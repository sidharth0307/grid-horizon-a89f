"""Day-ahead alignment and forecast-error analytics.

Convention everywhere: error = forecast - actual.
Positive error = over-forecast = shortfall the desk must buy in balancing markets.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.database import get_db_connection

LONDON = ZoneInfo("Europe/London")

PERSISTENCE_LAG = pd.Timedelta(hours=48)  # always known at D-1 gate closure
DEBIAS_WINDOW_DAYS = 7                    # trailing window of delivery days
DEBIAS_LAG_DAYS = 2                       # actuals are final only through D-2 at D-1 gate closure
DEBIAS_MIN_PERIODS = 48                   # require at least one day of finalised errors
WARMUP_DAYS = 10                          # history loaded before date_from for baselines

ALIGNED_COLUMNS = [
    "startTime", "actual_mw", "forecast_mw", "publishTime", "horizon_h",
    "error_mw", "abs_error_mw", "persist_actual_mw", "persist_error_mw",
    "delivery_date", "trailing_bias", "bias_adjusted_mw", "bias_adj_error_mw",
]


def parse_time_str(time_str: str) -> time:
    """Parse 'HH:MM' into a datetime.time. Raises ValueError on invalid input."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Time must be in HH:MM format")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Hour must be 0-23 and minute must be 0-59")
    return time(h, m)


def cutoff_utc(delivery_day: date, gate: time) -> pd.Timestamp:
    """UTC instant of the D-1 gate closure (gate is Europe/London wall-clock time)."""
    local_cutoff = datetime.combine(delivery_day - timedelta(days=1), gate, tzinfo=LONDON)
    return pd.Timestamp(local_cutoff).tz_convert("UTC")


def load_data_from_db(
    date_from: Optional[str] = None, date_to: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Read raw actuals and forecasts, keeping WARMUP_DAYS of history before date_from."""
    conn = get_db_connection()
    try:
        df_act = pd.read_sql_query(
            "SELECT start_time AS startTime, generation_mw AS generation FROM actual_generation", conn
        )
        df_fc = pd.read_sql_query(
            "SELECT publish_time AS publishTime, start_time AS startTime, generation_mw AS generation "
            "FROM forecast_generation",
            conn,
        )
    finally:
        conn.close()

    df_act["startTime"] = pd.to_datetime(df_act["startTime"], utc=True)
    df_fc["publishTime"] = pd.to_datetime(df_fc["publishTime"], utc=True)
    df_fc["startTime"] = pd.to_datetime(df_fc["startTime"], utc=True)

    if date_from:
        floor = pd.to_datetime(date_from, utc=True) - pd.Timedelta(days=WARMUP_DAYS)
        df_act = df_act[df_act["startTime"] >= floor]
        df_fc = df_fc[df_fc["startTime"] >= floor]
    if date_to:
        end_ts = pd.to_datetime(date_to, utc=True)
        df_act = df_act[df_act["startTime"] <= end_ts]
        df_fc = df_fc[df_fc["startTime"] <= end_ts]

    return df_act, df_fc


def align_forecasts_as_of(df_forecasts: pd.DataFrame, gate_closure: time = time(9, 20)) -> pd.DataFrame:
    """Latest forecast per target with publishTime <= D-1 gate closure (no lookahead).

    WINDFOR is hourly: each hourly value is applied to both half-hour settlement periods
    of its hour (step function). Ties on publishTime keep the last row in input order.
    """
    empty = pd.DataFrame(columns=["startTime", "publishTime", "forecast_mw", "horizon_h"])
    if df_forecasts.empty:
        return empty

    fc = df_forecasts.copy()
    fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)
    fc["publishTime"] = pd.to_datetime(fc["publishTime"], utc=True)

    delivery_days = fc["startTime"].dt.tz_convert(LONDON).dt.date
    cutoffs = {d: cutoff_utc(d, gate_closure) for d in delivery_days.unique()}
    fc["cutoff_utc"] = delivery_days.map(cutoffs)

    eligible = fc.loc[fc["publishTime"] <= fc["cutoff_utc"]].copy()
    if eligible.empty:
        return empty

    eligible["horizon_h"] = (eligible["startTime"] - eligible["publishTime"]).dt.total_seconds() / 3600.0
    latest = (
        eligible.sort_values("publishTime", kind="stable")
        .drop_duplicates("startTime", keep="last")
        .rename(columns={"generation": "forecast_mw"})[["startTime", "publishTime", "forecast_mw", "horizon_h"]]
    )

    if (latest["startTime"].dt.minute == 0).all():
        second_half = latest.copy()
        second_half["startTime"] = second_half["startTime"] + pd.Timedelta(minutes=30)
        second_half["horizon_h"] = second_half["horizon_h"] + 0.5
        latest = pd.concat([latest, second_half]).sort_values("startTime").reset_index(drop=True)

    return latest


def add_walk_forward_debias(merged: pd.DataFrame) -> pd.DataFrame:
    """Causal bias correction.

    For delivery day d the correction is the mean error over delivery days
    d-8 .. d-2 (7 days): at D-1 09:20 only actuals through D-2 are final.
    With fewer than DEBIAS_MIN_PERIODS finalised errors there is no correction (NaN) -
    never a whole-sample fallback, which would leak future data.
    """
    out = merged.copy()
    out["delivery_date"] = out["startTime"].dt.tz_convert(LONDON).dt.date

    errors = out.dropna(subset=["error_mw"])
    daily = errors.groupby("delivery_date")["error_mw"].agg(["sum", "count"]) if not errors.empty else None

    bias_by_day: Dict[date, float] = {}
    for d in out["delivery_date"].unique():
        bias = np.nan
        if daily is not None:
            days = [d - timedelta(days=k) for k in range(DEBIAS_LAG_DAYS, DEBIAS_LAG_DAYS + DEBIAS_WINDOW_DAYS)]
            hist = daily.reindex(days).dropna()
            n = hist["count"].sum() if not hist.empty else 0
            if n >= DEBIAS_MIN_PERIODS:
                bias = float(hist["sum"].sum() / n)
        bias_by_day[d] = bias

    out["trailing_bias"] = out["delivery_date"].map(bias_by_day).astype(float)
    out["bias_adjusted_mw"] = (out["forecast_mw"] - out["trailing_bias"]).clip(lower=0.0)
    out["bias_adj_error_mw"] = (out["bias_adjusted_mw"] - out["actual_mw"]).abs()
    return out


def build_aligned_timeseries(
    df_actuals: pd.DataFrame,
    df_aligned_forecasts: pd.DataFrame,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """Outer-join actuals and as-of forecasts, then add persistence and debias columns."""
    if df_actuals.empty and df_aligned_forecasts.empty:
        return pd.DataFrame(columns=ALIGNED_COLUMNS)

    act = df_actuals.rename(columns={"generation": "actual_mw"}).copy()
    fc = df_aligned_forecasts.copy()
    if not act.empty:
        act["startTime"] = pd.to_datetime(act["startTime"], utc=True)
        act = act.drop_duplicates("startTime", keep="last")
    if not fc.empty:
        fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)

    merged = pd.merge(act, fc, on="startTime", how="outer").sort_values("startTime").reset_index(drop=True)
    merged["error_mw"] = merged["forecast_mw"] - merged["actual_mw"]
    merged["abs_error_mw"] = merged["error_mw"].abs()

    # 48 h persistence: actual at (startTime - 48 h), matched on timestamp not row position
    lookup = act[["startTime", "actual_mw"]].rename(
        columns={"actual_mw": "persist_actual_mw", "startTime": "lookup_time"}
    )
    merged["lookup_time"] = merged["startTime"] - PERSISTENCE_LAG
    merged = pd.merge(merged, lookup, on="lookup_time", how="left").drop(columns=["lookup_time"])
    merged["persist_error_mw"] = (merged["persist_actual_mw"] - merged["actual_mw"]).abs()

    merged = add_walk_forward_debias(merged)

    if date_from:
        merged = merged[merged["startTime"] >= pd.to_datetime(date_from, utc=True)]
    if date_to:
        merged = merged[merged["startTime"] <= pd.to_datetime(date_to, utc=True)]
    return merged


def _null_metrics(total_periods: int) -> Dict:
    return {
        "total_periods": total_periods, "paired_periods": 0, "coverage_pct": 0.0,
        "mae_mw": None, "rmse_mw": None, "mean_bias_mw": None, "wape_pct": None,
        "over_forecast_share_pct": None,
        "max_shortfall_risk_mw": None, "max_surplus_mw": None,
        "p10_error_mw": None, "p50_error_mw": None, "p90_error_mw": None,
        "persistence_mae_mw": None, "skill_score_pct": None,
        "debiased_mae_mw": None, "debiased_improvement_pct": None, "debiased_periods": 0,
    }


def compute_metrics(df: pd.DataFrame) -> Dict:
    """Error KPIs, P90 shortfall buffer, persistence skill and walk-forward debias result."""
    total_periods = len(df)
    paired = df.dropna(subset=["actual_mw", "forecast_mw"])
    valid_count = len(paired)
    if valid_count == 0:
        return _null_metrics(total_periods)

    actual_sum = float(paired["actual_mw"].sum())
    mae = float(paired["abs_error_mw"].mean())
    rmse = float(np.sqrt((paired["error_mw"] ** 2).mean()))
    bias = float(paired["error_mw"].mean())
    wape = round(float(paired["abs_error_mw"].sum()) / actual_sum * 100, 2) if actual_sum > 0 else None
    over_share = round(float((paired["error_mw"] > 0).mean()) * 100, 1)

    # P90 of shortfall events only (positive errors)
    positive = paired.loc[paired["error_mw"] > 0, "error_mw"]
    p90_buffer = round(float(np.percentile(positive, 90)), 2) if len(positive) > 0 else 0.0

    # Persistence skill, on identical periods
    persist_mae = model_mae_matched = skill = None
    if "persist_actual_mw" in paired.columns:
        pe = paired.dropna(subset=["persist_actual_mw"])
        if not pe.empty:
            persist_mae = float(pe["persist_error_mw"].mean())
            model_mae_matched = float(pe["abs_error_mw"].mean())
            if persist_mae > 0:
                skill = round((1 - model_mae_matched / persist_mae) * 100, 2)

    # Walk-forward debias, compared with raw MAE on the same periods
    debiased_mae = debiased_impr = None
    debiased_n = 0
    if "bias_adj_error_mw" in paired.columns:
        de = paired.dropna(subset=["bias_adj_error_mw"])
        debiased_n = len(de)
        if debiased_n:
            debiased_mae = float(de["bias_adj_error_mw"].mean())
            raw_same_rows = float(de["abs_error_mw"].mean())
            if raw_same_rows > 0:
                debiased_impr = round((1 - debiased_mae / raw_same_rows) * 100, 2)

    return {
        "total_periods": total_periods,
        "paired_periods": valid_count,
        "coverage_pct": round(valid_count / total_periods * 100, 2) if total_periods else 0.0,
        "mae_mw": round(mae, 2),
        "rmse_mw": round(rmse, 2),
        "mean_bias_mw": round(bias, 2),
        "wape_pct": wape,
        "over_forecast_share_pct": over_share,
        "max_shortfall_risk_mw": round(float(paired["error_mw"].max()), 2),
        "max_surplus_mw": round(float(paired["error_mw"].min()), 2),
        "p10_error_mw": round(float(np.percentile(paired["error_mw"], 10)), 2),
        "p50_error_mw": round(float(np.percentile(paired["error_mw"], 50)), 2),
        "p90_error_mw": p90_buffer,
        "persistence_mae_mw": round(persist_mae, 2) if persist_mae is not None else None,
        "skill_score_pct": skill,
        "debiased_mae_mw": round(debiased_mae, 2) if debiased_mae is not None else None,
        "debiased_improvement_pct": debiased_impr,
        "debiased_periods": debiased_n,
    }


def compute_horizon_breakdown(df: pd.DataFrame) -> List[Dict]:
    """Error by delivery block (Europe/London). With a fixed gate, block and lead time are tied together."""
    paired = df.dropna(subset=["actual_mw", "forecast_mw"]).copy()
    if paired.empty:
        return []

    paired["delivery_hour"] = paired["startTime"].dt.tz_convert(LONDON).dt.hour
    bins = [0, 7, 13, 19, 24]
    labels = ["Overnight (00-06)", "Morning Ramp (07-12)", "Afternoon (13-18)", "Evening Peak (19-23)"]
    paired["period_block"] = pd.cut(paired["delivery_hour"], bins=bins, labels=labels, right=False)

    breakdown = []
    for block_name, group in paired.groupby("period_block", observed=False):
        if len(group) == 0:
            continue
        lead = float(group["horizon_h"].mean()) if "horizon_h" in group else 0.0
        breakdown.append({
            "horizon_bucket": str(block_name),
            "mae_mw": round(float(group["abs_error_mw"].mean()), 2),
            "bias_mw": round(float(group["error_mw"].mean()), 2),
            "avg_lead_time_h": round(lead, 1),
            "count": len(group),
        })
    return breakdown
