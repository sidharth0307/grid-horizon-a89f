import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "elexon_jan2026.sqlite"

def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Actuals table from FUELHH (fuelType == 'WIND')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actual_generation (
            start_time TEXT PRIMARY KEY,
            generation_mw REAL NOT NULL
        )
    """)
    
    # Forecasts table from WINDFOR
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecast_generation (
            publish_time TEXT NOT NULL,
            start_time TEXT NOT NULL,
            generation_mw REAL NOT NULL,
            PRIMARY KEY (publish_time, start_time)
        )
    """)
    
    # Indexes for fast range lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_start_time ON forecast_generation(start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_publish_time ON forecast_generation(publish_time)")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")