"""SQLite persistence layer with fallback paths for OneDrive/cloud environments."""
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional


def _pick_db_path() -> Path:
    env = os.environ.get("AIRSIGHT_DB")
    if env:
        return Path(env)
    # Try project folder first
    project = Path(__file__).parent / "airfares.db"
    try:
        project.parent.mkdir(parents=True, exist_ok=True)
        project.touch(exist_ok=True)
        return project
    except OSError:
        pass
    # Fallback to a writable user profile folder
    fallback = Path.home() / ".airsight" / "airfares.db"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


DB_PATH: Path = _pick_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS fares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_date TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    advance_days INTEGER NOT NULL,
    carrier TEXT NOT NULL,
    base_fare REAL NOT NULL,
    tax REAL NOT NULL,
    total_fare REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'live',
    scraped_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fares_scrape ON fares(scrape_date, origin, destination, advance_days);

CREATE TABLE IF NOT EXISTS cpi_series (
    month TEXT PRIMARY KEY,
    cpi_index REAL NOT NULL,
    yoy_change REAL,
    source TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def row_count(table: str = "fares") -> int:
    with get_conn() as conn:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def scrape_dates() -> List[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT DISTINCT scrape_date FROM fares ORDER BY scrape_date DESC")
        return [r[0] for r in cur.fetchall()]


def insert_fare(row: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO fares
            (scrape_date, origin, destination, departure_date, advance_days,
             carrier, base_fare, tax, total_fare, source, scraped_at)
            VALUES (:scrape_date, :origin, :destination, :departure_date, :advance_days,
                    :carrier, :base_fare, :tax, :total_fare, :source, :scraped_at)
            """,
            row,
        )


def load_fares(scrape_date: Optional[str] = None) -> List[sqlite3.Row]:
    sql = "SELECT * FROM fares"
    params: tuple = ()
    if scrape_date:
        sql += " WHERE scrape_date = ?"
        params = (scrape_date,)
    sql += " ORDER BY scrape_date DESC, origin, destination, advance_days, total_fare"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def load_cpi() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM cpi_series ORDER BY month"
        ).fetchall()


def ensure_tables() -> None:
    init_db()
