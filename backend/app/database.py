import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "elexon_jan2026.sqlite"


def get_db_connection(readonly: bool = True, path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the snapshot. The API opens it read-only (safe on read-only filesystems such as serverless)."""
    if readonly:
        if not path.exists():
            raise FileNotFoundError(f"Data snapshot not found: {path}")
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def db_version(path: Path = DB_PATH) -> int:
    """Cache key that changes whenever the snapshot file is replaced."""
    return path.stat().st_mtime_ns if path.exists() else 0


def init_db(path: Path = DB_PATH) -> None:
    conn = get_db_connection(readonly=False, path=path)
    cursor = conn.cursor()

    # Actuals from FUELHH (fuelType == 'WIND')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actual_generation (
            start_time TEXT PRIMARY KEY,
            generation_mw REAL NOT NULL
        )
    """)

    # Forecasts from WINDFOR
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecast_generation (
            publish_time TEXT NOT NULL,
            start_time TEXT NOT NULL,
            generation_mw REAL NOT NULL,
            PRIMARY KEY (publish_time, start_time)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_start_time ON forecast_generation(start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_publish_time ON forecast_generation(publish_time)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")
