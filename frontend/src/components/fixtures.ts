import type { KPIResponse } from '../types/api';

export function metricsFixture(overrides: Partial<KPIResponse> = {}): KPIResponse {
  return {
    total_periods: 1488,
    paired_periods: 1488,
    coverage_pct: 100,
    mae_mw: 2041.96,
    rmse_mw: 2509.06,
    mean_bias_mw: 1747.89,
    wape_pct: 18.1,
    over_forecast_share_pct: 84.7,
    max_shortfall_risk_mw: 6900,
    max_surplus_mw: -3000,
    p10_error_mw: -300,
    p50_error_mw: 1700,
    p90_error_mw: 4341,
    persistence_mae_mw: 4344.96,
    skill_score_pct: 53.0,
    debiased_mae_mw: 1670.2,
    debiased_improvement_pct: 15.22,
    debiased_periods: 1488,
    ...overrides,
  };
}
