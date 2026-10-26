from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import analytics

app = FastAPI(
    title="UK Day-Ahead Wind Evaluation Platform API",
    description="Elexon BMRS day-ahead wind forecast error evaluation with strict anti-leakage gate cutoffs.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "wind-eval-engine", "version": "1.0.0"}