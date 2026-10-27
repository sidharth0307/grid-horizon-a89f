"""API contract, validation, CORS and snapshot-backed golden numbers."""
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import analytics

client = TestClient(app)

MONTH = {"date_from": "2026-01-02T00:00:00Z", "date_to": "2026-02-01T23:30:00Z"}


def strict_json(text: str):
    """Parse JSON refusing NaN/Infinity, which browsers cannot parse."""
    def refuse(token):
        raise ValueError(f"non-finite number in JSON: {token}")
    return json.loads(text, parse_constant=refuse)


def test_health_reports_snapshot():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["snapshot"]["actual_rows"] > 1488 and body["snapshot"]["forecast_runs"] > 100


def test_meta_matches_scope():
    meta = client.get("/api/meta").json()
    assert meta["actuals_count"] == 1488
    assert meta["min_delivery_date"] == "2026-01-02T00:00:00Z"


@pytest.mark.parametrize("params", [
    {"gate_cutoff": "banana"}, {"gate_cutoff": "25:99"}, {"gate_cutoff": "9:20"},
    {"date_from": "not-a-date"},
    {"date_from": "2026-01-10T00:00:00Z", "date_to": "2026-01-09T00:00:00Z"},   # reversed
    {"date_from": "2025-12-30T00:00:00Z"},                                      # before scope
    {"date_to": "2026-02-02T23:30:00Z"},                                        # after scope
])
@pytest.mark.parametrize("path", ["/api/metrics", "/api/series", "/api/breakdown", "/api/export.csv"])
def test_bad_input_is_rejected_with_422(path, params):
    assert client.get(path, params=params).status_code == 422


def test_month_metrics_golden_numbers():
    m = client.get("/api/metrics").json()
    assert (m["total_periods"], m["paired_periods"], m["coverage_pct"]) == (1488, 1488, 100.0)
    assert m["mae_mw"] == 2041.96 and m["rmse_mw"] == 2509.06 and m["mean_bias_mw"] == 1747.89
    assert m["wape_pct"] == 18.1 and m["p90_error_mw"] == 4341.0
    assert m["over_forecast_share_pct"] == 84.7
    assert m["skill_score_pct"] == 53.0


def test_gate_choice_selects_the_expected_forecast_run():
    """09:30 run is published after 09:20 but before 09:50; no run between 09:50 and 11:00."""
    mae = {g: client.get("/api/metrics", params={"gate_cutoff": g}).json()["mae_mw"] for g in ("09:20", "09:50", "11:00")}
    assert mae["09:50"] == mae["11:00"] == 2016.31
    assert mae["09:20"] == 2041.96
    runs = {g: {p["publishTime"][11:16] for p in client.get("/api/series", params={"gate_cutoff": g}).json()}
            for g in ("09:20", "09:50")}
    assert "07:30" in runs["09:20"] and "09:30" not in runs["09:20"]
    assert "09:30" in runs["09:50"]


def test_series_is_strict_json_complete_and_causal():
    r = client.get("/api/series", params=MONTH)
    data = strict_json(r.text)
    assert len(data) == 1488
    assert all(p["publishTime"] for p in data)
    assert all(p["horizon_h"] is not None and p["horizon_h"] > 0 for p in data)
    # every forecast was published before the next day's 09:20 London gate (UTC == London in January)
    for p in data:
        gate_day = date.fromisoformat(p["startTime"][:10]) - timedelta(days=1)
        assert p["publishTime"][:16] <= f"{gate_day.isoformat()}T09:20"


def test_debiased_metric_only_counts_periods_with_history():
    m = client.get("/api/metrics").json()
    assert 0 < m["debiased_periods"] <= 1488
    assert m["debiased_improvement_pct"] > 0


def test_breakdown_covers_every_period():
    items = client.get("/api/breakdown").json()
    assert sum(i["count"] for i in items) == 1488
    assert {i["horizon_bucket"] for i in items} == {
        "Overnight (00-06)", "Morning Ramp (07-12)", "Afternoon (13-18)", "Evening Peak (19-23)"}


def test_csv_export_columns_and_rows():
    r = client.get("/api/export.csv", params={"gate_cutoff": "09:50"})
    lines = r.text.strip().splitlines()
    assert lines[0].split(",") == analytics.CSV_COLUMNS
    assert len(lines) == 1489
    assert "wind_forecast_eval_gate0950_2026-01-02_2026-02-01.csv" in r.headers["content-disposition"]


def test_cached_frames_cannot_be_corrupted_by_callers():
    df = analytics._get_processed_data(None, None, "09:20")
    df["error_mw"] = 0.0
    assert client.get("/api/metrics").json()["mae_mw"] == 2041.96


def test_cors_allows_only_configured_origins_and_no_credentials():
    ok = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" not in ok.headers
    evil = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers


def test_every_response_carries_timing_header():
    assert float(client.get("/api/health").headers["x-process-time-ms"]) >= 0
