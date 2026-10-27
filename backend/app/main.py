import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_VERSION, SCOPE_END, SCOPE_START, cors_origins
from app.database import get_db_connection
from app.routers import analytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("wind_eval")

app = FastAPI(
    title="UK Day-Ahead Wind Evaluation Platform API",
    description="Elexon BMRS day-ahead wind forecast error evaluation with strict anti-leakage gate cutoffs.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    logger.info("%s %s -> %s in %.1f ms", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


app.include_router(analytics.router)


@app.get("/api/health")
def health():
    """Liveness plus a check that the data snapshot is present and populated."""
    try:
        conn = get_db_connection()
        try:
            actuals = conn.execute("SELECT COUNT(*) FROM actual_generation").fetchone()[0]
            forecasts = conn.execute("SELECT COUNT(*) FROM forecast_generation").fetchone()[0]
            runs = conn.execute("SELECT COUNT(DISTINCT publish_time) FROM forecast_generation").fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:  # missing or unreadable snapshot
        logger.error("health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Data snapshot unavailable") from exc
    if actuals == 0 or forecasts == 0:
        raise HTTPException(status_code=503, detail="Data snapshot is empty")
    return {
        "status": "ok",
        "service": "wind-eval-engine",
        "version": APP_VERSION,
        "scope": {"from": SCOPE_START, "to": SCOPE_END},
        "snapshot": {"actual_rows": actuals, "forecast_rows": forecasts, "forecast_runs": runs},
    }
