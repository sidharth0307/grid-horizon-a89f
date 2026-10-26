import pytest
from datetime import datetime, time
import pandas as pd
from app.services.engine import (
    align_forecasts_as_of,
    build_aligned_timeseries,
    compute_metrics,
    cutoff_utc
)

@pytest.fixture
def sample_forecast_data():
    return pd.DataFrame([
        # Target delivery: 2026-01-05 12:00 UTC. 
        # Cutoff (09:20 London time on 2026-01-04): 2026-01-04 09:20:00 UTC
        {"publishTime": "2026-01-04 08:00:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 4000.0},
        {"publishTime": "2026-01-04 09:19:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 4500.0}, # Valid latest before gate
        {"publishTime": "2026-01-04 09:21:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 9999.0}, # Leaked! (must be excluded)
        
        # Target delivery: 2026-01-05 12:30 UTC
        {"publishTime": "2026-01-04 09:20:00+00:00", "startTime": "2026-01-05 12:30:00+00:00", "generation": 5000.0}, # Exact boundary
    ])

def test_leakage_rejection(sample_forecast_data):
    """Verifies that a forecast published 1 minute after the 09:20 cutoff is strictly rejected."""
    aligned = align_forecasts_as_of(sample_forecast_data, gate_closure=time(9, 20))
    target_row = aligned[aligned["startTime"] == "2026-01-05 12:00:00+00:00"].iloc[0]
    
    assert target_row["forecast_mw"] == 4500.0
    assert target_row["forecast_mw"] != 9999.0

def test_boundary_exact_inclusion(sample_forecast_data):
    """Verifies that a forecast published exactly at 09:20 is included."""
    aligned = align_forecasts_as_of(sample_forecast_data, gate_closure=time(9, 20))
    target_row = aligned[aligned["startTime"] == "2026-01-05 12:30:00+00:00"].iloc[0]
    
    assert target_row["forecast_mw"] == 5000.0

def test_outer_join_preserves_unpaired():
    """Verifies that missing forecasts or missing actuals do not drop rows (no silent data loss)."""
    actuals = pd.DataFrame([{"startTime": "2026-01-06 00:00:00+00:00", "generation": 3000.0}])
    forecasts = pd.DataFrame(columns=["startTime", "publishTime", "generation"])
    
    aligned = align_forecasts_as_of(forecasts)
    df_merged = build_aligned_timeseries(actuals, aligned)
    
    assert len(df_merged) == 1
    assert pd.isna(df_merged.iloc[0]["forecast_mw"])
    assert df_merged.iloc[0]["actual_mw"] == 3000.0

def test_sign_convention_shortfall_risk():
    """Verifies that over-forecasting (Forecast > Actual) results in positive error and positive bias."""
    df = pd.DataFrame([
        {
            "startTime": pd.to_datetime("2026-01-05 12:00:00+00:00"),
            "actual_mw": 1000.0,
            "forecast_mw": 1300.0,
            "error_mw": 300.0,
            "abs_error_mw": 300.0,
            "persist_actual_mw": 900.0,
            "persist_error_mw": 100.0
        }
    ])
    metrics = compute_metrics(df)
    assert metrics["mae_mw"] == 300.0
    assert metrics["mean_bias_mw"] == 300.0
    assert metrics["max_shortfall_risk_mw"] == 300.0
    assert metrics["wape_pct"] == 30.0

def test_empty_dataframe_returns_null_safe_metrics():
    """Verifies that empty results return typed nulls instead of throwing 500 exceptions."""
    empty_df = pd.DataFrame(columns=["startTime", "actual_mw", "forecast_mw", "error_mw", "abs_error_mw"])
    metrics = compute_metrics(empty_df)
    assert metrics["total_periods"] == 0
    assert metrics["paired_periods"] == 0
    assert metrics["mae_mw"] is None