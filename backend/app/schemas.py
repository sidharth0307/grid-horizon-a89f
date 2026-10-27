from typing import Optional
from pydantic import BaseModel, Field

class TimeSeriesPoint(BaseModel):
    startTime: str = Field(..., description="Target delivery settlement period (ISO UTC)")
    actual_mw: Optional[float] = Field(None, description="Actual wind generation outturn in MW")
    forecast_mw: Optional[float] = Field(None, description="Day-ahead forecast in MW as of gate closure")
    bias_adjusted_mw: Optional[float] = Field(None, description="Forecast minus trailing 7-day walk-forward bias (delivery days D-8..D-2); null without history")
    publishTime: Optional[str] = Field(None, description="Timestamp when the forecast was issued")
    error_mw: Optional[float] = Field(None, description="Forecast - Actual (Positive = Shortfall Risk)")
    abs_error_mw: Optional[float] = Field(None, description="Absolute error in MW")
    horizon_h: Optional[float] = Field(None, description="Forecast lead time in hours")

class KPIResponse(BaseModel):
    total_periods: int
    paired_periods: int
    coverage_pct: float
    mae_mw: Optional[float]
    rmse_mw: Optional[float]
    mean_bias_mw: Optional[float]
    wape_pct: Optional[float]
    over_forecast_share_pct: Optional[float] = Field(None, description="Share of periods where forecast > actual")
    max_shortfall_risk_mw: Optional[float]
    max_surplus_mw: Optional[float]
    p10_error_mw: Optional[float]
    p50_error_mw: Optional[float]
    p90_error_mw: Optional[float]
    persistence_mae_mw: Optional[float]
    skill_score_pct: Optional[float]
    debiased_mae_mw: Optional[float] = Field(None, description="MAE after trailing 7-day walk-forward bias correction, on periods with enough history")
    debiased_improvement_pct: Optional[float] = Field(None, description="MAE reduction vs raw forecast on the same periods")
    debiased_periods: Optional[int] = Field(None, description="Periods with a causal bias correction available")

class HorizonBreakdownItem(BaseModel):
    horizon_bucket: str
    mae_mw: float
    bias_mw: float
    avg_lead_time_h: Optional[float] = Field(None, description="Average forecast lead time in hours")
    count: int

class MetaResponse(BaseModel):
    min_delivery_date: str
    max_delivery_date: str
    default_gate_closure: str
    actuals_count: int
    forecasts_count: int