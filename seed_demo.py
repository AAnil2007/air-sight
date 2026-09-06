"""Seeds clearly-labelled demo fares + CPI months so the dashboard is
usable before the live scraper has collected history.

Every seeded row carries source='DemoSeed' so demo data is never confused
with scraped EaseMyTrip observations.
"""
import hashlib
from datetime import date, timedelta

from database import get_conn, init_db, insert_cpi, insert_fares
from routes_config import ADVANCE_WINDOWS, CARRIER_NAMES, ROUTES

BASE_FARES = {
    ("DEL", "BOM"): 5600,
    ("DEL", "BLR"): 6400,
    ("BOM", "BLR"): 4700,
    ("DEL", "CCU"): 6100,
    ("BLR", "HYD"): 3900,
    ("MAA", "DEL"): 7000,
}

CARRIER_OFFSET = {"6E": 1.00, "IX": 0.94, "QP": 0.97, "AI": 1.12, "SG": 1.05}
DEMO_SOURCE = "DemoSeed"


def _jitter(*parts: str) -> float:
    """Deterministic pseudo-random factor in roughly +/-5%."""
    digest = hashlib.md5("|".join(parts).encode()).hexdigest()
    return 1 + ((int(digest[:8], 16) % 1000) / 1000 - 0.5) * 0.10


def _advance_factor(days_ahead: int) -> float:
    return {1: 1.45, 7: 1.18, 15: 1.05, 30: 0.96, 45: 0.92}.get(days_ahead, 1.0)


def seed_fares(days: int = 60) -> int:
    init_db()
    conn = get_conn()
    conn.execute("DELETE FROM fares WHERE source = ?", (DEMO_SOURCE,))
    conn.commit()
    conn.close()

    today = date.today()
    records = []
    for offset in range(days - 1, -1, -1):
        scrape_day = today - timedelta(days=offset)
        scrape_date = scrape_day.isoformat()
        # gentle seasonal drift so the index actually moves
        drift = 1 + (days - 1 - offset) * 0.0018

        for route in ROUTES:
            base = BASE_FARES[route]
            for days_ahead in ADVANCE_WINDOWS:
                travel_date = (scrape_day + timedelta(days=days_ahead)).strftime("%d/%m/%Y")
                for code, offset_factor in CARRIER_OFFSET.items():
                    total = (base * drift * offset_factor
                             * _advance_factor(days_ahead)
                             * _jitter(scrape_date, "".join(route), code, str(days_ahead)))
                    total = round(total, 2)
                    base_component = round(total / 1.28, 2)
                    records.append({
                        "origin": route[0],
                        "dest": route[1],
                        "carrier_code": code,
                        "carrier_name": CARRIER_NAMES.get(code, code),
                        "scrape_date": scrape_date,
                        "travel_date": travel_date,
                        "advance_days": days_ahead,
                        "fare_class": "Economy",
                        "base_fare": base_component,
                        "taxes": round(total - base_component, 2),
                        "total_fare": total,
                        "stops": 0,
                        "source": DEMO_SOURCE,
                    })

    insert_fares(records)
    return len(records)


CPI_ROWS = [
    ("2025-10", 193.4, 178.2), ("2025-11", 194.1, 178.9),
    ("2025-12", 194.8, 179.6), ("2026-01", 195.6, 180.4),
    ("2026-02", 196.2, 181.0), ("2026-03", 196.9, 181.8),
    ("2026-04", 197.7, 182.5), ("2026-05", 198.4, 183.3),
    ("2026-06", 199.2, 184.1), ("2026-07", 200.0, 184.9),
    ("2026-08", 200.7, 185.6), ("2026-09", 201.5, 186.4),
]


def seed_cpi() -> int:
    init_db()
    rows = [{"month": m, "cpi_general": g, "cpi_transport": t} for m, g, t in CPI_ROWS]
    insert_cpi(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"seeded {seed_fares()} demo fare rows and {seed_cpi()} CPI months")
