"""Build the SQLite snapshot from the Elexon BMRS Insights API (real data only).

Run from the backend directory:  python -m scripts.ingest_elexon

The snapshot is built in a temporary file and swapped in atomically, so a failed
run never destroys the existing database. There is no synthetic fallback.
"""
import asyncio
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, List, Tuple

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import DB_PATH, init_db  # noqa: E402

BASE_URL_FUELHH = "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
BASE_URL_WINDFOR = "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"

# Scope: delivery 2026-01-02 .. 2026-02-01 (decisions made in January 2026).
# A warm-up window before the scope gives the 48 h persistence baseline and the
# 7-day walk-forward debiaser history from the first delivery day onward.
ACTUALS_DATE_FROM = "2025-12-22"
ACTUALS_DATE_TO = "2026-02-02"
FC_PUBLISH_FROM = "2025-12-22T00:00:00Z"
FC_PUBLISH_TO = "2026-02-01T23:59:59Z"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def canon_ts(value: str) -> str:
    """Canonical UTC timestamp string, e.g. 2026-01-02T00:30:00Z."""
    return pd.to_datetime(value, utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")


def _records(payload: Any) -> List[dict]:
    return payload if isinstance(payload, list) else payload.get("data", [])


def parse_fuelhh(payload: Any) -> List[Tuple[str, float]]:
    """(start_time, MW) for fuelType == WIND."""
    rows = []
    for item in _records(payload):
        if str(item.get("fuelType", "")).upper() != "WIND":
            continue
        start, gen = item.get("startTime"), item.get("generation")
        if start and gen is not None:
            rows.append((canon_ts(start), float(gen)))
    return rows


def parse_windfor(payload: Any) -> List[Tuple[str, str, float]]:
    """(publish_time, start_time, MW)."""
    rows = []
    for item in _records(payload):
        pub, start, gen = item.get("publishTime"), item.get("startTime"), item.get("generation")
        if pub and start and gen is not None:
            rows.append((canon_ts(pub), canon_ts(start), float(gen)))
    return rows


async def fetch_json(client: httpx.AsyncClient, url: str, params: dict, retries: int = 3) -> Any:
    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, params=params, headers={"Accept": "application/json"}, timeout=120.0)
        except httpx.TransportError as exc:
            if attempt == retries:
                raise RuntimeError(f"Network error fetching {url}: {exc}") from exc
            await asyncio.sleep(2 ** attempt)
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code in RETRYABLE_STATUS and attempt < retries:
            await asyncio.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"Elexon request failed ({response.status_code}) for {url}: {response.text[:300]}")
    raise RuntimeError(f"Exhausted retries for {url}")  # pragma: no cover


async def build_snapshot(client: httpx.AsyncClient, target: Path) -> dict:
    """Fetch, validate and write a complete snapshot to `target` (atomic swap)."""
    tmp = target.with_name(target.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        actual_rows = parse_fuelhh(await fetch_json(
            client, BASE_URL_FUELHH,
            {"settlementDateFrom": ACTUALS_DATE_FROM, "settlementDateTo": ACTUALS_DATE_TO},
        ))
        if not actual_rows:
            raise RuntimeError("Zero WIND records parsed from FUELHH. Check the API schema.")

        forecast_rows = parse_windfor(await fetch_json(
            client, BASE_URL_WINDFOR,
            {"publishDateTimeFrom": FC_PUBLISH_FROM, "publishDateTimeTo": FC_PUBLISH_TO},
        ))
        if not forecast_rows:
            raise RuntimeError("Zero records parsed from WINDFOR. Check the API schema.")

        init_db(tmp)
        conn = sqlite3.connect(tmp)
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO actual_generation (start_time, generation_mw) VALUES (?, ?)", actual_rows
            )
            conn.executemany(
                "INSERT OR REPLACE INTO forecast_generation (publish_time, start_time, generation_mw) VALUES (?, ?, ?)",
                forecast_rows,
            )
            conn.commit()
            audit = {
                "actual_rows": conn.execute("SELECT COUNT(*) FROM actual_generation").fetchone()[0],
                "actual_window": conn.execute("SELECT MIN(start_time), MAX(start_time) FROM actual_generation").fetchone(),
                "forecast_rows": conn.execute("SELECT COUNT(*) FROM forecast_generation").fetchone()[0],
                "forecast_runs": conn.execute("SELECT COUNT(DISTINCT publish_time) FROM forecast_generation").fetchone()[0],
                "publish_window": conn.execute("SELECT MIN(publish_time), MAX(publish_time) FROM forecast_generation").fetchone(),
                "publish_cadence": conn.execute(
                    "SELECT substr(publish_time, 12, 5), COUNT(DISTINCT publish_time) "
                    "FROM forecast_generation GROUP BY 1 ORDER BY 1"
                ).fetchall(),
                "target_minutes": conn.execute(
                    "SELECT substr(start_time, 15, 2), COUNT(*) FROM forecast_generation GROUP BY 1"
                ).fetchall(),
            }
        finally:
            conn.close()
        os.replace(tmp, target)
        return audit
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def print_audit(audit: dict) -> None:
    print("\n--- INGESTION AUDIT ---")
    print(f"Actual rows:   {audit['actual_rows']} ({audit['actual_window'][0]} to {audit['actual_window'][1]})")
    print(f"Forecast rows: {audit['forecast_rows']} from {audit['forecast_runs']} runs "
          f"({audit['publish_window'][0]} to {audit['publish_window'][1]})")
    print("Run cadence (UTC hh:mm -> distinct runs):", ", ".join(f"{h}={n}" for h, n in audit["publish_cadence"]))
    print("Target minutes (:00 only means hourly):", ", ".join(f"{m}={n}" for m, n in audit["target_minutes"]))
    print("-----------------------\n")


async def main() -> None:
    print(f"Target database: {DB_PATH}")
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits) as client:
        audit = await build_snapshot(client, DB_PATH)
    print_audit(audit)


if __name__ == "__main__":
    asyncio.run(main())
