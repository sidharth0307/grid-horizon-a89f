import io
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import pandas as pd

from app.database import get_db_connection
from app.schemas import HorizonBreakdownItem, KPIResponse, MetaResponse, TimeSeriesPoint
from app.services.engine import (
    align_forecasts_as_of,
    build_aligned_timeseries,
    compute_horizon_breakdown,
    compute_metrics,
    load_data_from_db,
    parse_time_str
)

router = APIRouter(prefix="/api", tags=["Analytics"])

DEFAULT_START = "2026-01-02T00:00:00Z"
DEFAULT_END = "2026-02-01T23:30:00Z"

def validate_date(date_str: Optional[str], param_name: str):
    if not date_str:
        return
    try:
        pd.to_datetime(date_str)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format for '{param_name}'. Must be ISO-8601 UTC string."
        )

def validate_cutoff(cutoff_str: str):
    if not re.match(r"^\d{2}:\d{2}$", cutoff_str):
        raise HTTPException(
            status_code=422,
            detail="gate_cutoff must be in HH:MM format (e.g. 09:20)"
        )
    try:
        return parse_time_str(cutoff_str)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/meta", response_model=MetaResponse)
def get_metadata():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT MIN(start_time), MAX(start_time), COUNT(*) FROM actual_generation WHERE start_time >= ? AND start_time <= ?", (DEFAULT_START, DEFAULT_END))
    row_act = c.fetchone()
    c.execute("SELECT COUNT(*) FROM forecast_generation WHERE start_time >= ? AND start_time <= ?", (DEFAULT_START, DEFAULT_END))
    fc_count = c.fetchone()[0]
    conn.close()
    
    return MetaResponse(
        min_delivery_date=DEFAULT_START,
        max_delivery_date=DEFAULT_END,
        default_gate_closure="09:20",
        actuals_count=row_act[2] if row_act else 1488,
        forecasts_count=fc_count
    )

def _get_processed_data(date_from: Optional[str], date_to: Optional[str], cutoff_str: str):
    validate_date(date_from, "date_from")
    validate_date(date_to, "date_to")
    gate = validate_cutoff(cutoff_str)
    
    start = date_from if date_from else DEFAULT_START
    end = date_to if date_to else DEFAULT_END
    
    df_act, df_fc = load_data_from_db(start, end)
    aligned_fc = align_forecasts_as_of(df_fc, gate_closure=gate)
    return build_aligned_timeseries(df_act, aligned_fc, start, end)

@router.get("/metrics", response_model=KPIResponse)
def get_metrics(
    date_from: Optional[str] = Query(None, description="Start timestamp ISO UTC"),
    date_to: Optional[str] = Query(None, description="End timestamp ISO UTC"),
    gate_cutoff: str = Query("09:20", description="HH:MM gate closure in Europe/London time")
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    return compute_metrics(df)

@router.get("/series", response_model=List[TimeSeriesPoint])
def get_series(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query("09:20")
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    df_clean = df.replace({float("nan"): None})
    
    records = []
    for _, row in df_clean.iterrows():
        records.append(TimeSeriesPoint(
            startTime=str(row["startTime"].isoformat()),
            actual_mw=row["actual_mw"],
            forecast_mw=row["forecast_mw"],
            publishTime=str(row["publishTime"].isoformat()) if "publishTime" in row and pd.notna(row["publishTime"]) else None,
            error_mw=row["error_mw"],
            abs_error_mw=row["abs_error_mw"],
            horizon_h=row["horizon_h"] if "horizon_h" in row and pd.notna(row["horizon_h"]) else None
        ))
    return records

@router.get("/breakdown", response_model=List[HorizonBreakdownItem])
def get_breakdown(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query("09:20")
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    return compute_horizon_breakdown(df)

@router.get("/export.csv")
def export_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query("09:20")
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    filename = f"wind_forecast_eval_jan2026_{gate_cutoff.replace(':', '')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )