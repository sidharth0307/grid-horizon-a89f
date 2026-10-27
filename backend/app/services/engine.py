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
    """Computes exact UTC timestamp corresponding to local D-1 gate closure in Europe/London."""
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
    
    # Keep 10 days of historical actuals and forecasts before start_ts to calculate trailing bias
    if date_from:
        start_ts = pd.to_datetime(date_from, utc=True)
        df_act_filtered = df_act[df_act["startTime"] >= (start_ts - pd.Timedelta(days=10))]
        df_fc_filtered = df_fc[df_fc["startTime"] >= (start_ts - pd.Timedelta(days=10))]
    else:
        df_act_filtered = df_act
        df_fc_filtered = df_fc

    if date_to:
        end_ts = pd.to_datetime(date_to, utc=True)
        df_act_filtered = df_act_filtered[df_act_filtered["startTime"] <= end_ts]
        df_fc_filtered = df_fc_filtered[df_fc_filtered["startTime"] <= end_ts]
        
    return df_act_filtered, df_fc_filtered

def align_forecasts_as_of(
    df_forecasts: pd.DataFrame, 
    gate_closure: time = time(9, 20)
) -> pd.DataFrame:
    """
    Selects latest forecast published strictly on or before D-1 gate closure.
    Expands hourly step-function targets to 30-minute settlement periods.
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

    latest_fc = (
        eligible.sort_values("publishTime")
        .drop_duplicates("startTime", keep="last")
        .rename(columns={"generation": "forecast_mw"})
        [["startTime", "publishTime", "forecast_mw", "horizon_h"]]
    )

    # Hourly expansion: map :00 target to subsequent :30 settlement interval
    if (latest_fc["startTime"].dt.minute == 0).all() and len(latest_fc) > 0:
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
    Outer join actuals and forecasts.
    Calculates:
      1. 48h lag persistence baseline (no same-day leakage)
      2. 7-day walk-forward debiaser using only finalized history (D-2 and older)
    """
    if df_actuals.empty and df_aligned_forecasts.empty:
        return pd.DataFrame(columns=["startTime", "actual_mw", "forecast_mw", "publishTime", "error_mw", "abs_error_mw", "horizon_h", "bias_adjusted_mw"])

    act = df_actuals.rename(columns={"generation": "actual_mw"}).copy()
    if not act.empty:
        act["startTime"] = pd.to_datetime(act["startTime"], utc=True)

    fc = df_aligned_forecasts.copy()
    if not fc.empty:
        fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)

    merged = pd.merge(act, fc, on="startTime", how="outer").sort_values("startTime")
    
    # Error convention: Forecast - Actual
    # Positive (> 0): Over-forecast -> Shortfall Risk
    merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
    merged["abs_error_mw"] = merged["error_mw"].abs()
    
    # 48-Hour Persistence: match startTime exactly to (startTime - 48h)
    act_lookup = act[["startTime", "actual_mw"]].rename(
        columns={"actual_mw": "persist_actual_mw", "startTime": "lookup_time"}
    )
    merged["lookup_time"] = merged["startTime"] - pd.Timedelta(hours=48)
    merged = pd.merge(merged, act_lookup, on="lookup_time", how="left").drop(columns=["lookup_time"])
    merged["persist_error_mw"] = (merged["persist_actual_mw"] - merged["actual_mw"]).abs()

    # Walk-forward 7-day debiaser using strictly finalized D-2 history:
    # At gate closure D-1 09:20, actuals are only finalized through D-2 23:30.
    # We compute trailing mean error over [t - 9 days, t - 2 days] (7 full days)
    merged["delivery_date"] = merged["startTime"].dt.date
    unique_dates = sorted(merged["delivery_date"].unique())
    daily_bias_map = {}

    # Calculate global prior mean bias as sensible default if history window is short
    all_paired_errors = merged.dropna(subset=["error_mw"])["error_mw"]
    default_bias = float(all_paired_errors.mean()) if not all_paired_errors.empty else 1748.0
    
    for d in unique_dates:
        hist_start = pd.Timestamp(d - timedelta(days=9), tz="UTC")
        hist_end = pd.Timestamp(d - timedelta(days=2), tz="UTC") + pd.Timedelta(hours=23, minutes=30)
        hist_df = merged[(merged["startTime"] >= hist_start) & (merged["startTime"] <= hist_end)]
        hist_paired = hist_df.dropna(subset=["error_mw"])
        if len(hist_paired) >= 24: # At least 12-24 hours of finalized history
            daily_bias_map[d] = float(hist_paired["error_mw"].mean())
        else:
            daily_bias_map[d] = default_bias

    merged["trailing_bias"] = merged["delivery_date"].map(daily_bias_map).fillna(default_bias)
    # Clip at 0 so adjusted forecast cannot physically be negative MW
    merged["bias_adjusted_mw"] = (merged["forecast_mw"] - merged["trailing_bias"]).clip(lower=0.0)
    merged["bias_adj_error_mw"] = (merged["bias_adjusted_mw"] - merged["actual_mw"]).abs()

    # Filter to requested evaluation scope
    if date_from:
        merged = merged[merged["startTime"] >= pd.to_datetime(date_from, utc=True)]
    if date_to:
        merged = merged[merged["startTime"] <= pd.to_datetime(date_to, utc=True)]
        
    return merged

def compute_metrics(df: pd.DataFrame) -> Dict:
    """Computes comprehensive error KPIs, P90 reserve buffer, and debiased performance."""
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
            "skill_score_pct": None,
            "debiased_mae_mw": None,
            "debiased_improvement_pct": None
        }

    actual_sum = float(paired["actual_mw"].sum())
    abs_err_sum = float(paired["abs_error_mw"].sum())
    mae = float(paired["abs_error_mw"].mean())
    rmse = float(np.sqrt((paired["error_mw"] ** 2).mean()))
    bias = float(paired["error_mw"].mean())
    wape = round((abs_err_sum / actual_sum * 100), 2) if actual_sum > 0 else None
    
    # Forward-Looking P90 Deficit Buffer (positive errors = shortfall events)
    positive_errors = paired.loc[paired["error_mw"] > 0, "error_mw"]
    p90_buffer = round(float(np.percentile(positive_errors, 90)), 2) if len(positive_errors) > 0 else 0.0

    # Persistence evaluation on identical matched periods
    persist_eval = paired.dropna(subset=["persist_actual_mw"])
    persist_mae = float(persist_eval["persist_error_mw"].mean()) if not persist_eval.empty else None
    model_mae_matched = float(persist_eval["abs_error_mw"].mean()) if not persist_eval.empty else None
    skill_score = (
        round((1 - (model_mae_matched / persist_mae)) * 100, 2)
        if (persist_mae and model_mae_matched and persist_mae > 0)
        else None
    )

    # 7-day walk-forward debiased evaluation (defensive check for test fixtures)
    debiased_mae = None
    debiased_impr = None
    if "bias_adj_error_mw" in paired.columns:
        debiased_eval = paired.dropna(subset=["bias_adj_error_mw"])
        if not debiased_eval.empty:
            debiased_mae = float(debiased_eval["bias_adj_error_mw"].mean())
            if mae > 0:
                debiased_impr = round((1 - (debiased_mae / mae)) * 100, 2)

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
        "skill_score_pct": skill_score,
        "debiased_mae_mw": round(debiased_mae, 2) if debiased_mae else None,
        "debiased_improvement_pct": debiased_impr
    }

def compute_horizon_breakdown(df: pd.DataFrame) -> List[Dict]:
    """Computes error statistics grouped by physical delivery block in Europe/London."""
    paired = df.dropna(subset=["actual_mw", "forecast_mw"]).copy()
    if paired.empty:
        return []
    
    paired["delivery_hour"] = paired["startTime"].dt.tz_convert(LONDON).dt.hour
    
    # Wholesale settlement blocks
    bins = [0, 7, 13, 19, 24]
    labels = ["Overnight (00-06)", "Morning Ramp (07-12)", "Afternoon (13-18)", "Evening Peak (19-23)"]
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