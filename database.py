"""SQLite storage layer for the Airsight airfare price index prototype."""
import os
import sqlite3
import tempfile
from pathlib import Path


def _candidate_paths():
    env = os.environ.get("AIRSIGHT_DB")
    if env:
        yield Path(env)
    yield Path(__file__).resolve().with_name("airfares.db")
    yield Path.home() / ".airsight" / "airfares.db"
    yield Path(tempfile.gettempdir()) / "airsight" / "airfares.db"


def _open(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        # Cloud-synced folders (OneDrive/Dropbox) can reject WAL files.
        conn.execute("PRAGMA journal_mode=DELETE")
    return conn


DB_PATH = next(iter(_candidate_paths()))


def get_conn():
    """Open the database, falling back to a writable location.

    Folders synced by OneDrive/Dropbox, or paths with non-ASCII characters,
    sometimes refuse SQLite writes; we then use a per-user data directory.
    """
    global DB_PATH
    errors = []
    for path in _candidate_paths():
        try:
            conn = _open(path)
            DB_PATH = path
            return conn
        except (sqlite3.OperationalError, OSError) as exc:
            errors.append(f"{path}: {exc}")
    raise sqlite3.OperationalError(
        "Could not open a database file. Tried:\n  " + "\n  ".join(errors)
    )


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT, dest TEXT,
            carrier_code TEXT, carrier_name TEXT,
            scrape_date TEXT, travel_date TEXT, advance_days INTEGER,
            fare_class TEXT,
            base_fare REAL, taxes REAL, total_fare REAL,
            stops INTEGER,
            source TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cpi_series (
            month TEXT PRIMARY KEY,
            cpi_general REAL,
            cpi_transport REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fares_scrape
        ON fares (scrape_date, origin, dest)
    """)
    conn.commit()
    conn.close()


def insert_fares(records: list[dict]):
    if not records:
        return
    conn = get_conn()
    conn.executemany("""
        INSERT INTO fares (origin, dest, carrier_code, carrier_name,
                            scrape_date, travel_date, advance_days,
                            fare_class, base_fare, taxes, total_fare,
                            stops, source)
        VALUES (:origin,:dest,:carrier_code,:carrier_name,
                :scrape_date,:travel_date,:advance_days,
                :fare_class,:base_fare,:taxes,:total_fare,
                :stops,:source)
    """, records)
    conn.commit()
    conn.close()


def insert_cpi(rows: list[dict]):
    if not rows:
        return
    conn = get_conn()
    conn.executemany("""
        INSERT OR REPLACE INTO cpi_series (month, cpi_general, cpi_transport)
        VALUES (:month, :cpi_general, :cpi_transport)
    """, rows)
    conn.commit()
    conn.close()


def scrape_dates() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT scrape_date FROM fares ORDER BY scrape_date"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def row_count() -> int:
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM fares").fetchone()[0]
    except sqlite3.OperationalError:
        n = 0
    conn.close()
    return n
