from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class TimeSeriesPoint(BaseModel):
    startTime: str = Field(..., description="Target delivery settlement period (ISO UTC)")
    actual_mw: Optional[float] = Field(None, description="Actual wind generation outturn in MW")
    forecast_mw: Optional[float] = Field(None, description="Day-ahead forecast in MW as of gate closure")
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
    max_shortfall_risk_mw: Optional[float]
    max_surplus_mw: Optional[float]
    p10_error_mw: Optional[float]
    p50_error_mw: Optional[float]
    p90_error_mw: Optional[float]
    persistence_mae_mw: Optional[float]
    skill_score_pct: Optional[float]

class HorizonBreakdownItem(BaseModel):
    horizon_bucket: str
    mae_mw: float
    bias_mw: float
    count: int

class MetaResponse(BaseModel):
    min_delivery_date: str
    max_delivery_date: str
    default_gate_closure: str
    actuals_count: int
    forecasts_count: int