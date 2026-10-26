import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
import httpx

# Ensure parent directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import DB_PATH, init_db

# Official Elexon Insights Solution API v1 Endpoints
BASE_URL_FUELHH = "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
BASE_URL_WINDFOR = "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"

# Target Windows
# Delivery dates: 2026-01-02 00:00:00Z to 2026-02-01 23:30:00Z (Jan 2026 Decisions)
ACTUALS_DATE_FROM = "2025-12-30"  # Pulling from Jan 1 provides the 48h lag baseline for Jan 3+
ACTUALS_DATE_TO = "2026-02-02"

# Pull forecasts starting 2025-12-31 to cover D-1 gate closures for Jan 2 delivery
FC_PUBLISH_FROM = "2025-12-31T00:00:00Z"
FC_PUBLISH_TO = "2026-02-01T23:59:59Z"

async def ingest_actuals(client: httpx.AsyncClient, conn: sqlite3.Connection):
    print("Fetching real Actual Generation (FUELHH) from data.elexon.co.uk...")
    params = {
        "settlementDateFrom": ACTUALS_DATE_FROM,
        "settlementDateTo": ACTUALS_DATE_TO
    }
    
    headers = {"Accept": "application/json"}
    response = await client.get(BASE_URL_FUELHH, params=params, headers=headers, timeout=120.0)
    
    if response.status_code != 200:
        raise RuntimeError(f"Elexon FUELHH fetch failed with status {response.status_code}: {response.text[:300]}")
    
    data = response.json()
    records = data if isinstance(data, list) else data.get("data", [])
    
    actual_rows = []
    for item in records:
        if str(item.get("fuelType", "")).upper() == "WIND":
            start_time = item.get("startTime")
            gen = item.get("generation")
            if start_time and gen is not None:
                actual_rows.append((start_time, float(gen)))

    if not actual_rows:
        raise RuntimeError("Zero wind records parsed from FUELHH response. Check API schema.")

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO actual_generation (start_time, generation_mw)
        VALUES (?, ?)
    """, actual_rows)
    conn.commit()
    print(f"-> Successfully inserted {len(actual_rows)} real actual generation records.")

async def ingest_forecasts(client: httpx.AsyncClient, conn: sqlite3.Connection):
    print("Fetching real Forecast Generation (WINDFOR) from data.elexon.co.uk...")
    params = {
        "publishDateTimeFrom": FC_PUBLISH_FROM,
        "publishDateTimeTo": FC_PUBLISH_TO
    }
    
    headers = {"Accept": "application/json"}
    response = await client.get(BASE_URL_WINDFOR, params=params, headers=headers, timeout=120.0)
    
    if response.status_code != 200:
        raise RuntimeError(f"Elexon WINDFOR fetch failed with status {response.status_code}: {response.text[:300]}")
    
    data = response.json()
    records = data if isinstance(data, list) else data.get("data", [])
    
    fc_rows = []
    for item in records:
        pub_time = item.get("publishTime")
        start_time = item.get("startTime")
        gen = item.get("generation")
        if pub_time and start_time and gen is not None:
            fc_rows.append((pub_time, start_time, float(gen)))

    if not fc_rows:
        raise RuntimeError("Zero forecast records parsed from WINDFOR response. Check API schema.")

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO forecast_generation (publish_time, start_time, generation_mw)
        VALUES (?, ?, ?)
    """, fc_rows)
    conn.commit()
    print(f"-> Successfully inserted {len(fc_rows)} real forecast generation records.")

async def main():
    print(f"Target Database: {DB_PATH}")
    # Reset DB to eradicate mock data
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Existing database deleted.")
        
    init_db()
    conn = sqlite3.connect(DB_PATH)
    
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits) as client:
        await ingest_actuals(client, conn)
        await ingest_forecasts(client, conn)
        
    # Audit printouts
    cursor = conn.cursor()
    actual_count = cursor.execute("SELECT COUNT(*) FROM actual_generation").fetchone()[0]
    fc_count = cursor.execute("SELECT COUNT(*) FROM forecast_generation").fetchone()[0]
    distinct_pub = cursor.execute("SELECT COUNT(DISTINCT publish_time) FROM forecast_generation").fetchone()[0]
    min_act = cursor.execute("SELECT MIN(start_time), MAX(start_time) FROM actual_generation").fetchone()
    min_fc = cursor.execute("SELECT MIN(publish_time), MAX(publish_time) FROM forecast_generation").fetchone()
    conn.close()
    
    print("\n--- INGESTION AUDIT ---")
    print(f"Actual Generation Rows: {actual_count} (Window: {min_act[0]} to {min_act[1]})")
    print(f"Forecast Generation Rows: {fc_count}")
    print(f"Distinct Publish Times: {distinct_pub} (Window: {min_fc[0]} to {min_fc[1]})")
    print("------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())