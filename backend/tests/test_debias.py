"""Walk-forward debiaser: causality, window definition and metric semantics."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.services.engine import add_walk_forward_debias, compute_metrics


def make_frame(error_by_day: dict, base_actual: float = 10000.0) -> pd.DataFrame:
    """48 half-hours per delivery day (UTC == London in winter); forecast = actual + day error."""
    rows = []
    for day, err in error_by_day.items():
        start = pd.Timestamp(day, tz="UTC")
        for i in range(48):
            actual = base_actual
            rows.append({
                "startTime": start + pd.Timedelta(minutes=30 * i),
                "actual_mw": actual,
                "forecast_mw": actual + err,
                "error_mw": err,
            })
    return pd.DataFrame(rows)


def days(start: date, n: int):
    return [start + timedelta(days=i) for i in range(n)]


def bias_for(df: pd.DataFrame, day: date) -> float:
    return df.loc[df["delivery_date"] == day, "trailing_bias"].iloc[0]


def test_window_is_delivery_days_d_minus_8_to_d_minus_2():
    ds = days(date(2026, 1, 1), 20)
    errors = {d: 100.0 * (i + 1) for i, d in enumerate(ds)}  # Jan 1 -> 100, Jan 2 -> 200, ...
    out = add_walk_forward_debias(make_frame(errors))
    # Jan 15: window Jan 7..Jan 13 -> errors 700..1300 -> mean 1000
    assert bias_for(out, date(2026, 1, 15)) == 1000.0


def test_yesterday_and_today_never_enter_the_correction():
    ds = days(date(2026, 1, 1), 20)
    base = {d: 100.0 * (i + 1) for i, d in enumerate(ds)}
    changed = dict(base)
    changed[date(2026, 1, 14)] = 99999.0  # D-1
    changed[date(2026, 1, 15)] = -99999.0  # D itself
    a = add_walk_forward_debias(make_frame(base))
    b = add_walk_forward_debias(make_frame(changed))
    assert bias_for(a, date(2026, 1, 15)) == bias_for(b, date(2026, 1, 15))


def test_future_days_do_not_leak_into_early_days():
    """Regression: a whole-sample fallback used to move the first day's correction."""
    ds = days(date(2026, 1, 1), 25)
    base = {d: 500.0 for d in ds}
    changed = dict(base)
    for d in ds[15:]:
        changed[d] = 20000.0  # wreck late-month errors
    a = add_walk_forward_debias(make_frame(base))
    b = add_walk_forward_debias(make_frame(changed))
    for d in (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 10)):
        x, y = bias_for(a, d), bias_for(b, d)
        assert (np.isnan(x) and np.isnan(y)) or x == y


def test_no_history_means_no_correction_not_a_fallback():
    out = add_walk_forward_debias(make_frame({d: 500.0 for d in days(date(2026, 1, 1), 5)}))
    # Jan 1 and Jan 2 have no finalised history (window needs Jan 1 at the earliest for Jan 3)
    assert np.isnan(bias_for(out, date(2026, 1, 1)))
    assert np.isnan(bias_for(out, date(2026, 1, 2)))
    assert bias_for(out, date(2026, 1, 3)) == 500.0  # exactly one full day of history is enough
    first = out[out["delivery_date"] == date(2026, 1, 2)]
    assert first["bias_adjusted_mw"].isna().all()


def test_adjusted_forecast_is_never_negative():
    out = add_walk_forward_debias(make_frame({d: 20000.0 for d in days(date(2026, 1, 1), 6)}, base_actual=100.0))
    assert (out["bias_adjusted_mw"].dropna() >= 0).all()


def test_improvement_is_measured_on_the_same_rows_as_the_raw_error():
    df = pd.DataFrame([
        {"startTime": pd.Timestamp("2026-01-05 00:00", tz="UTC"), "actual_mw": 1000.0, "forecast_mw": 1100.0,
         "error_mw": 100.0, "abs_error_mw": 100.0, "bias_adj_error_mw": np.nan},
        {"startTime": pd.Timestamp("2026-01-05 00:30", tz="UTC"), "actual_mw": 1000.0, "forecast_mw": 1200.0,
         "error_mw": 200.0, "abs_error_mw": 200.0, "bias_adj_error_mw": 50.0},
    ])
    m = compute_metrics(df)
    assert m["debiased_periods"] == 1
    assert m["debiased_mae_mw"] == 50.0
    assert m["debiased_improvement_pct"] == 75.0  # vs 200 on that row, not vs the 150 overall MAE
