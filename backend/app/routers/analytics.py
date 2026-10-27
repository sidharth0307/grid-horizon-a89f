import io
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import DEFAULT_GATE, SCOPE_END, SCOPE_START
from app.database import db_version, get_db_connection
from app.schemas import HorizonBreakdownItem, KPIResponse, MetaResponse, TimeSeriesPoint
from app.services.engine import (
    align_forecasts_as_of,
    build_aligned_timeseries,
    compute_horizon_breakdown,
    compute_metrics,
    load_data_from_db,
    parse_time_str,
)

router = APIRouter(prefix="/api", tags=["Analytics"])

GATE_PATTERN = r"^\d{2}:\d{2}$"
_SCOPE_START_TS = pd.Timestamp(SCOPE_START)
_SCOPE_END_TS = pd.Timestamp(SCOPE_END)

CSV_COLUMNS = [
    "startTime", "actual_mw", "forecast_mw", "publishTime", "horizon_h",
    "error_mw", "abs_error_mw", "bias_adjusted_mw", "persist_actual_mw",
]


def _parse_ts(value: Optional[str], default: str, name: str) -> pd.Timestamp:
    try:
        return pd.to_datetime(value or default, utc=True)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid date for '{name}'. Use an ISO-8601 UTC timestamp."
        ) from exc


def _resolve_window(date_from: Optional[str], date_to: Optional[str]) -> Tuple[str, str]:
    start = _parse_ts(date_from, SCOPE_START, "date_from")
    end = _parse_ts(date_to, SCOPE_END, "date_to")
    if start > end:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to.")
    if start < _SCOPE_START_TS or end > _SCOPE_END_TS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must lie within the evaluation scope {SCOPE_START} to {SCOPE_END}.",
        )
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_gate(gate_cutoff: str):
    try:
        return parse_time_str(gate_cutoff)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@lru_cache(maxsize=64)
def _aligned_cached(start: str, end: str, gate: str, snapshot_version: int) -> pd.DataFrame:
    df_act, df_fc = load_data_from_db(start, end)
    aligned = align_forecasts_as_of(df_fc, gate_closure=parse_time_str(gate))
    return build_aligned_timeseries(df_act, aligned, start, end)


def _get_processed_data(date_from: Optional[str], date_to: Optional[str], gate_cutoff: str) -> pd.DataFrame:
    start, end = _resolve_window(date_from, date_to)
    _resolve_gate(gate_cutoff)
    # Cache key includes the snapshot mtime so a re-ingest is picked up; callers get a private copy.
    return _aligned_cached(start, end, gate_cutoff, db_version()).copy()


def _clean(value: Any) -> Any:
    """NaN/NaT -> None; Timestamps -> ISO strings (strict JSON has no NaN)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


@router.get("/meta", response_model=MetaResponse)
def get_metadata():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM actual_generation WHERE start_time >= ? AND start_time <= ?",
            (SCOPE_START, SCOPE_END),
        )
        actuals = c.fetchone()[0]
        c.execute(
            "SELECT COUNT(*) FROM forecast_generation WHERE start_time >= ? AND start_time <= ?",
            (SCOPE_START, SCOPE_END),
        )
        forecasts = c.fetchone()[0]
    finally:
        conn.close()
    return MetaResponse(
        min_delivery_date=SCOPE_START,
        max_delivery_date=SCOPE_END,
        default_gate_closure=DEFAULT_GATE,
        actuals_count=actuals,
        forecasts_count=forecasts,
    )


@router.get("/metrics", response_model=KPIResponse)
def get_metrics(
    date_from: Optional[str] = Query(None, description="Start timestamp, ISO UTC"),
    date_to: Optional[str] = Query(None, description="End timestamp, ISO UTC"),
    gate_cutoff: str = Query(DEFAULT_GATE, pattern=GATE_PATTERN, description="HH:MM gate closure, Europe/London"),
):
    return compute_metrics(_get_processed_data(date_from, date_to, gate_cutoff))


@router.get("/series", response_model=List[TimeSeriesPoint])
def get_series(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query(DEFAULT_GATE, pattern=GATE_PATTERN),
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    records: List[Dict[str, Any]] = df.reindex(columns=CSV_COLUMNS).to_dict("records")
    return [
        TimeSeriesPoint(**{k: _clean(v) for k, v in rec.items() if k != "persist_actual_mw"})
        for rec in records
    ]


@router.get("/breakdown", response_model=List[HorizonBreakdownItem])
def get_breakdown(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query(DEFAULT_GATE, pattern=GATE_PATTERN),
):
    return compute_horizon_breakdown(_get_processed_data(date_from, date_to, gate_cutoff))


@router.get("/export.csv")
def export_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    gate_cutoff: str = Query(DEFAULT_GATE, pattern=GATE_PATTERN),
):
    df = _get_processed_data(date_from, date_to, gate_cutoff)
    start, end = _resolve_window(date_from, date_to)
    out = df.reindex(columns=CSV_COLUMNS)
    numeric = out.select_dtypes("number").columns
    out[numeric] = out[numeric].round(2)
    buffer = io.StringIO()
    out.to_csv(buffer, index=False)
    filename = f"wind_forecast_eval_gate{gate_cutoff.replace(':', '')}_{start[:10]}_{end[:10]}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
