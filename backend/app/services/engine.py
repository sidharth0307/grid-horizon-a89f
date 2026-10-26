from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from app.database import get_db_connection

LONDON = ZoneInfo("Europe/London")

def parse_time_str(time_str: str) -> time:
    """Parses 'HH:MM' string into a datetime.time object."""
    try:
        parts = time_str.strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return time(9, 20)

def cutoff_utc(delivery_day: date, gate: time) -> pd.Timestamp:
    """Computes the exact UTC timestamp corresponding to local D-1 gate closure in Europe/London."""
    local_cutoff = datetime.combine(delivery_day - timedelta(days=1), gate, tzinfo=LONDON)
    return pd.Timestamp(local_cutoff).tz_convert("UTC")

def load_data_from_db(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Reads raw actuals and forecasts from SQLite."""
    conn = get_db_connection()
    
    query_act = "SELECT start_time as startTime, generation_mw as generation FROM actual_generation"
    query_fc = "SELECT publish_time as publishTime, start_time as startTime, generation_mw as generation FROM forecast_generation"
    
    df_act = pd.read_sql_query(query_act, conn)
    df_fc = pd.read_sql_query(query_fc, conn)
    conn.close()
    
    df_act["startTime"] = pd.to_datetime(df_act["startTime"], utc=True)
    df_fc["publishTime"] = pd.to_datetime(df_fc["publishTime"], utc=True)
    df_fc["startTime"] = pd.to_datetime(df_fc["startTime"], utc=True)
    
    if date_from:
        start_ts = pd.to_datetime(date_from, utc=True)
        df_act = df_act[df_act["startTime"] >= start_ts]
        df_fc = df_fc[df_fc["startTime"] >= start_ts]
    if date_to:
        end_ts = pd.to_datetime(date_to, utc=True)
        df_act = df_act[df_act["startTime"] <= end_ts]
        df_fc = df_fc[df_fc["startTime"] <= end_ts]
        
    return df_act, df_fc

def align_forecasts_as_of(
    df_forecasts: pd.DataFrame, 
    gate_closure: time = time(9, 20)
) -> pd.DataFrame:
    """
    Selects the latest forecast published strictly on or before D-1 gate closure.
    Immutable, vector-safe, and self-coerces datetimes.
    """
    if df_forecasts.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw", "horizon_h"])

    fc = df_forecasts.copy()
    
    # Defensive coercion to timezone-aware UTC datetime
    fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)
    fc["publishTime"] = pd.to_datetime(fc["publishTime"], utc=True)
    
    # Calculate target delivery day in London time
    delivery_days = fc["startTime"].dt.tz_convert(LONDON).dt.date
    cutoffs = {d: cutoff_utc(d, gate_closure) for d in delivery_days.unique()}
    fc["cutoff_utc"] = delivery_days.map(cutoffs)

    # Filter forecasts strictly published before or at the cutoff
    eligible = fc.loc[fc["publishTime"] <= fc["cutoff_utc"]].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw", "horizon_h"])

    # Compute lead time (horizon in hours)
    eligible["horizon_h"] = (eligible["startTime"] - eligible["publishTime"]).dt.total_seconds() / 3600.0

    # Retain the latest published forecast per settlement period
    latest_fc = (
        eligible.sort_values("publishTime")
        .drop_duplicates("startTime", keep="last")
        .rename(columns={"generation": "forecast_mw"})
        [["startTime", "publishTime", "forecast_mw", "horizon_h"]]
    )
    return latest_fc

def build_aligned_timeseries(
    df_actuals: pd.DataFrame, 
    df_aligned_forecasts: pd.DataFrame
) -> pd.DataFrame:
    """
    Merges actuals and forecasts using an outer join.
    Preserves missing gaps and future visibility.
    """
    if df_actuals.empty and df_aligned_forecasts.empty:
        return pd.DataFrame(columns=["startTime", "actual_mw", "forecast_mw", "error_mw", "abs_error_mw"])

    act = df_actuals.rename(columns={"generation": "actual_mw"}).copy()
    if not act.empty:
        act["startTime"] = pd.to_datetime(act["startTime"], utc=True)

    fc = df_aligned_forecasts.copy()
    if not fc.empty:
        fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)

    merged = pd.merge(act, fc, on="startTime", how="outer").sort_values("startTime")
    
    # Error convention: Forecast - Actual
    # Positive (> 0): Over-forecast -> Shortfall risk (utility must cover deficit)
    # Negative (< 0): Under-forecast -> Surplus
    merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
    merged["abs_error_mw"] = merged["error_mw"].abs()
    
    # Naive baseline: 24h persistence (48 half-hour settlement periods ago)
    merged["persist_actual_mw"] = merged["actual_mw"].shift(48)
    merged["persist_error_mw"] = (merged["persist_actual_mw"] - merged["actual_mw"]).abs()
    
    return merged

def compute_metrics(df: pd.DataFrame) -> Dict:
    """Computes comprehensive error KPIs and trading reserve metrics."""
    total_periods = len(df)
    paired = df.dropna(subset=["actual_mw", "forecast_mw"])
    valid_count = len(paired)
    
    if valid_count == 0:
        return {
            "total_periods": total_periods,
            "paired_periods": 0,
            "coverage_pct": 0.0,
            "mae_mw": None,
            "rmse_mw": None,
            "mean_bias_mw": None,
            "wape_pct": None,
            "max_shortfall_risk_mw": None,
            "max_surplus_mw": None,
            "p10_error_mw": None,
            "p50_error_mw": None,
            "p90_error_mw": None,
            "persistence_mae_mw": None,
            "skill_score_pct": None
        }

    actual_sum = float(paired["actual_mw"].sum())
    abs_err_sum = float(paired["abs_error_mw"].sum())
    mae = float(paired["abs_error_mw"].mean())
    rmse = float(np.sqrt((paired["error_mw"] ** 2).mean()))
    bias = float(paired["error_mw"].mean())
    wape = round((abs_err_sum / actual_sum * 100), 2) if actual_sum > 0 else None
    
    # Persistence evaluation
    valid_persist = df.dropna(subset=["actual_mw", "persist_actual_mw"])
    persist_mae = float(valid_persist["persist_error_mw"].mean()) if not valid_persist.empty else None
    skill_score = round((1 - (mae / persist_mae)) * 100, 2) if persist_mae and persist_mae > 0 else None

    return {
        "total_periods": total_periods,
        "paired_periods": valid_count,
        "coverage_pct": round((valid_count / total_periods) * 100, 2) if total_periods > 0 else 0.0,
        "mae_mw": round(mae, 2),
        "rmse_mw": round(rmse, 2),
        "mean_bias_mw": round(bias, 2),
        "wape_pct": wape,
        "max_shortfall_risk_mw": round(float(paired["error_mw"].max()), 2),
        "max_surplus_mw": round(float(paired["error_mw"].min()), 2),
        "p10_error_mw": round(float(np.percentile(paired["error_mw"], 10)), 2),
        "p50_error_mw": round(float(np.percentile(paired["error_mw"], 50)), 2),
        "p90_error_mw": round(float(np.percentile(paired["error_mw"], 90)), 2),
        "persistence_mae_mw": round(persist_mae, 2) if persist_mae else None,
        "skill_score_pct": skill_score
    }

def compute_horizon_breakdown(df: pd.DataFrame) -> List[Dict]:
    """Computes error statistics grouped by forecast lead-time buckets."""
    paired = df.dropna(subset=["actual_mw", "forecast_mw", "horizon_h"]).copy()
    if paired.empty:
        return []
    
    bins = [14, 20, 26, 32, 40]
    labels = ["14-20h (Early Morning)", "20-26h (Midday)", "26-32h (Evening Peak)", "32-38h (Late Night)"]
    paired["bucket"] = pd.cut(paired["horizon_h"], bins=bins, labels=labels, right=False)
    
    breakdown = []
    for bucket_name, group in paired.groupby("bucket", observed=False):
        if len(group) == 0:
            continue
        mae = float(group["abs_error_mw"].mean())
        bias = float(group["error_mw"].mean())
        breakdown.append({
            "horizon_bucket": str(bucket_name),
            "mae_mw": round(mae, 2),
            "bias_mw": round(bias, 2),
            "count": len(group)
        })
    return breakdown