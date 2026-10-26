from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from app.database import get_db_connection

LONDON = ZoneInfo("Europe/London")

def parse_time_str(time_str: str) -> time:
    """Parses 'HH:MM' string into a datetime.time object. Raises ValueError on invalid format."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Time must be in HH:MM format")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Hour must be 0-23 and minute must be 0-59")
    return time(h, m)

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
        # Keep an extra 2 days in actuals so that 48h persistence lookup has reference data
        df_act_filtered = df_act[df_act["startTime"] >= (start_ts - pd.Timedelta(days=2))]
        df_fc = df_fc[df_fc["startTime"] >= start_ts]
    else:
        df_act_filtered = df_act

    if date_to:
        end_ts = pd.to_datetime(date_to, utc=True)
        df_act_filtered = df_act_filtered[df_act_filtered["startTime"] <= end_ts]
        df_fc = df_fc[df_fc["startTime"] <= end_ts]
        
    return df_act_filtered, df_fc

def align_forecasts_as_of(
    df_forecasts: pd.DataFrame, 
    gate_closure: time = time(9, 20)
) -> pd.DataFrame:
    """
    Selects the latest forecast published strictly on or before D-1 gate closure.
    Expands hourly forecasts to cover both 30-minute settlement periods.
    """
    if df_forecasts.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw", "horizon_h"])

    fc = df_forecasts.copy()
    fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)
    fc["publishTime"] = pd.to_datetime(fc["publishTime"], utc=True)
    
    delivery_days = fc["startTime"].dt.tz_convert(LONDON).dt.date
    cutoffs = {d: cutoff_utc(d, gate_closure) for d in delivery_days.unique()}
    fc["cutoff_utc"] = delivery_days.map(cutoffs)

    eligible = fc.loc[fc["publishTime"] <= fc["cutoff_utc"]].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw", "horizon_h"])

    # Lead time in hours
    eligible["horizon_h"] = (eligible["startTime"] - eligible["publishTime"]).dt.total_seconds() / 3600.0

    # Pick latest forecast per timestamp
    latest_fc = (
        eligible.sort_values("publishTime")
        .drop_duplicates("startTime", keep="last")
        .rename(columns={"generation": "forecast_mw"})
        [["startTime", "publishTime", "forecast_mw", "horizon_h"]]
    )

    # Check if WINDFOR is hourly (all minutes == 0)
    if (latest_fc["startTime"].dt.minute == 0).all() and len(latest_fc) > 0:
        # Expand each hourly forecast to also cover the :30 half-hour settlement period
        fc_half_hour = latest_fc.copy()
        fc_half_hour["startTime"] = fc_half_hour["startTime"] + pd.Timedelta(minutes=30)
        fc_half_hour["horizon_h"] = fc_half_hour["horizon_h"] + 0.5
        latest_fc = pd.concat([latest_fc, fc_half_hour]).sort_values("startTime").reset_index(drop=True)

    return latest_fc

def build_aligned_timeseries(
    df_actuals: pd.DataFrame, 
    df_aligned_forecasts: pd.DataFrame,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> pd.DataFrame:
    """
    Merges actuals and forecasts via outer join.
    Applies timestamp-matched 48h persistence without lookahead leakage.
    """
    if df_actuals.empty and df_aligned_forecasts.empty:
        return pd.DataFrame(columns=["startTime", "actual_mw", "forecast_mw", "publishTime", "error_mw", "abs_error_mw", "horizon_h"])

    act = df_actuals.rename(columns={"generation": "actual_mw"}).copy()
    if not act.empty:
        act["startTime"] = pd.to_datetime(act["startTime"], utc=True)

    fc = df_aligned_forecasts.copy()
    if not fc.empty:
        fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)

    merged = pd.merge(act, fc, on="startTime", how="outer").sort_values("startTime")
    
    # Error convention: Forecast - Actual
    # Positive (> 0): Over-forecast -> Shortfall Risk (deficit requires thermal procurement)
    # Negative (< 0): Under-forecast -> Surplus
    merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
    merged["abs_error_mw"] = merged["error_mw"].abs()
    
    # 48-Hour Persistence: match startTime exactly to (startTime - 48h)
    act_lookup = act[["startTime", "actual_mw"]].rename(
        columns={"actual_mw": "persist_actual_mw", "startTime": "lookup_time"}
    )
    merged["lookup_time"] = merged["startTime"] - pd.Timedelta(hours=48)
    merged = pd.merge(merged, act_lookup, on="lookup_time", how="left").drop(columns=["lookup_time"])
    merged["persist_error_mw"] = (merged["persist_actual_mw"] - merged["actual_mw"]).abs()

    # Filter to requested display window
    if date_from:
        merged = merged[merged["startTime"] >= pd.to_datetime(date_from, utc=True)]
    if date_to:
        merged = merged[merged["startTime"] <= pd.to_datetime(date_to, utc=True)]
        
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
    
    # Forward-Looking P90 Deficit Buffer (positive error = shortfall)
    positive_errors = paired.loc[paired["error_mw"] > 0, "error_mw"]
    p90_buffer = round(float(np.percentile(positive_errors, 90)), 2) if len(positive_errors) > 0 else 0.0

    # Persistence evaluation on paired subset
    persist_eval = paired.dropna(subset=["persist_actual_mw"])
    persist_mae = float(persist_eval["persist_error_mw"].mean()) if not persist_eval.empty else None
    
    # Skill score compared strictly against the same paired intervals
    model_mae_matched = float(persist_eval["abs_error_mw"].mean()) if not persist_eval.empty else None
    skill_score = (
        round((1 - (model_mae_matched / persist_mae)) * 100, 2)
        if (persist_mae and model_mae_matched and persist_mae > 0)
        else None
    )

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
        "p90_error_mw": p90_buffer,
        "persistence_mae_mw": round(persist_mae, 2) if persist_mae else None,
        "skill_score_pct": skill_score
    }

def compute_horizon_breakdown(df: pd.DataFrame) -> List[Dict]:
    """Computes error statistics grouped by physical delivery hour (00:00 to 23:00)."""
    paired = df.dropna(subset=["actual_mw", "forecast_mw"]).copy()
    if paired.empty:
        return []
    
    paired["delivery_hour"] = paired["startTime"].dt.tz_convert(LONDON).dt.hour
    
    # Standard energy trading blocks
    bins = [0, 7, 13, 19, 24]
    labels = ["Overnight (00-06)", "Morning Ramp (07-12)", "Peak Afternoon (13-18)", "Evening Demand (19-23)"]
    paired["period_block"] = pd.cut(paired["delivery_hour"], bins=bins, labels=labels, right=False)
    
    breakdown = []
    for block_name, group in paired.groupby("period_block", observed=False):
        if len(group) == 0:
            continue
        mae = float(group["abs_error_mw"].mean())
        bias = float(group["error_mw"].mean())
        avg_lead_time = float(group["horizon_h"].mean()) if "horizon_h" in group else 0.0
        breakdown.append({
            "horizon_bucket": str(block_name),
            "mae_mw": round(mae, 2),
            "bias_mw": round(bias, 2),
            "avg_lead_time_h": round(avg_lead_time, 1),
            "count": len(group)
        })
    return breakdown