import pytest
from datetime import datetime, time
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.services.engine import (
    align_forecasts_as_of,
    build_aligned_timeseries,
    compute_metrics,
    parse_time_str
)

client = TestClient(app)

@pytest.fixture
def sample_forecast_data():
    return pd.DataFrame([
        {"publishTime": "2026-01-04 08:00:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 4000.0},
        {"publishTime": "2026-01-04 09:19:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 4500.0},
        {"publishTime": "2026-01-04 09:21:00+00:00", "startTime": "2026-01-05 12:00:00+00:00", "generation": 9999.0}, # Leaked
        {"publishTime": "2026-01-04 09:20:00+00:00", "startTime": "2026-01-05 12:30:00+00:00", "generation": 5000.0}, # Boundary exact
    ])

def test_leakage_rejection(sample_forecast_data):
    aligned = align_forecasts_as_of(sample_forecast_data, gate_closure=time(9, 20))
    target_row = aligned[aligned["startTime"] == "2026-01-05 12:00:00+00:00"].iloc[0]
    assert target_row["forecast_mw"] == 4500.0
    assert target_row["forecast_mw"] != 9999.0

def test_boundary_exact_inclusion(sample_forecast_data):
    aligned = align_forecasts_as_of(sample_forecast_data, gate_closure=time(9, 20))
    target_row = aligned[aligned["startTime"] == "2026-01-05 12:30:00+00:00"].iloc[0]
    assert target_row["forecast_mw"] == 5000.0

def test_outer_join_preserves_unpaired():
    actuals = pd.DataFrame([{"startTime": "2026-01-06 00:00:00+00:00", "generation": 3000.0}])
    forecasts = pd.DataFrame(columns=["startTime", "publishTime", "generation"])
    aligned = align_forecasts_as_of(forecasts)
    df_merged = build_aligned_timeseries(actuals, aligned)
    assert len(df_merged) == 1
    assert pd.isna(df_merged.iloc[0]["forecast_mw"])
    assert df_merged.iloc[0]["actual_mw"] == 3000.0

def test_sign_convention_shortfall_risk():
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
    assert metrics["mean_bias_mw"] == 300.0
    assert metrics["max_shortfall_risk_mw"] == 300.0
    assert metrics["wape_pct"] == 30.0

def test_true_48h_lag_persistence():
    """Confirms persistence lookup matches exactly 48 hours prior rather than leaky same-day lag."""
    t0 = pd.to_datetime("2026-01-03 10:00:00+00:00")
    t_lag = pd.to_datetime("2026-01-01 10:00:00+00:00")
    
    actuals = pd.DataFrame([
        {"startTime": t_lag, "generation": 5000.0},
        {"startTime": t0, "generation": 4200.0}
    ])
    forecasts = pd.DataFrame([
        {"publishTime": "2026-01-02 08:00:00+00:00", "startTime": t0, "generation": 4400.0}
    ])
    
    aligned = align_forecasts_as_of(forecasts)
    merged = build_aligned_timeseries(actuals, aligned, date_from="2026-01-03T00:00:00Z")
    
    row = merged[merged["startTime"] == t0].iloc[0]
    assert row["persist_actual_mw"] == 5000.0
    assert row["persist_error_mw"] == 800.0

def test_api_input_validation():
    """Confirms malformed gate cutoffs and bad dates return HTTP 422."""
    res_bad_cutoff = client.get("/api/metrics?gate_cutoff=25:99")
    assert res_bad_cutoff.status_code == 422
    
    res_bad_str = client.get("/api/metrics?gate_cutoff=banana")
    assert res_bad_str.status_code == 422
    
    res_bad_date = client.get("/api/metrics?date_from=not-a-date")
    assert res_bad_date.status_code == 422

def _fc(rows):
    return pd.DataFrame(rows, columns=["publishTime", "startTime", "generation"])

def test_hourly_forecast_expands_to_half_hours_with_same_publish_time():
    fc = _fc([("2026-01-04 08:30:00+00:00", "2026-01-05 12:00:00+00:00", 4500.0)])
    al = align_forecasts_as_of(fc, time(9, 20)).set_index("startTime")
    t0 = pd.Timestamp("2026-01-05 12:00:00+00:00")
    t1 = pd.Timestamp("2026-01-05 12:30:00+00:00")
    assert al.loc[t0, "forecast_mw"] == al.loc[t1, "forecast_mw"] == 4500.0
    assert al.loc[t0, "publishTime"] == al.loc[t1, "publishTime"]
    assert al.loc[t1, "horizon_h"] == al.loc[t0, "horizon_h"] + 0.5

def test_late_hourly_forecast_is_not_expanded_into_the_future():
    fc = _fc([("2026-01-04 09:30:00+00:00", "2026-01-05 12:00:00+00:00", 9999.0)])
    assert align_forecasts_as_of(fc, time(9, 20)).empty

def test_persistence_missing_when_lookup_actual_absent():
    act = pd.DataFrame([{"startTime": pd.Timestamp("2026-01-03 10:00:00+00:00"), "generation": 4200.0}])
    fc = _fc([("2026-01-02 08:00:00+00:00", "2026-01-03 10:00:00+00:00", 4400.0)])
    m = build_aligned_timeseries(act, align_forecasts_as_of(fc))
    assert m["persist_actual_mw"].isna().all()