"""Shared constants and environment-driven settings."""
import os

# Evaluation scope: purchase decisions made 1-31 Jan 2026 -> delivery 2 Jan 00:00 to 1 Feb 23:30 (UTC).
SCOPE_START = "2026-01-02T00:00:00Z"
SCOPE_END = "2026-02-01T23:30:00Z"

DEFAULT_GATE = "09:20"  # GB day-ahead (EPEX) gate closure, Europe/London

APP_VERSION = "1.1.0"


def cors_origins() -> list[str]:
    """Allowed browser origins. Set CORS_ORIGINS to a comma-separated list in deployment."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]
