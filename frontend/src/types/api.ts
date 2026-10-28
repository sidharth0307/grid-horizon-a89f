export interface TimeSeriesPoint {
  startTime: string;
  actual_mw: number | null;
  forecast_mw: number | null;
  bias_adjusted_mw?: number | null;
  publishTime?: string | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  horizon_h: number | null;
}

export interface KPIResponse {
  total_periods: number;
  paired_periods: number;
  coverage_pct: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  mean_bias_mw: number | null;
  wape_pct: number | null;
  over_forecast_share_pct?: number | null;
  max_shortfall_risk_mw: number | null;
  max_surplus_mw: number | null;
  p10_error_mw: number | null;
  p50_error_mw: number | null;
  p90_error_mw: number | null;
  persistence_mae_mw: number | null;
  skill_score_pct: number | null;
  debiased_mae_mw?: number | null;
  debiased_improvement_pct?: number | null;
  debiased_periods?: number | null;
}

export interface HorizonBreakdownItem {
  horizon_bucket: string;
  mae_mw: number;
  bias_mw: number;
  avg_lead_time_h?: number | null;
  count: number;
}

export interface DashboardData {
  metrics: KPIResponse;
  series: TimeSeriesPoint[];
  breakdown: HorizonBreakdownItem[];
}
