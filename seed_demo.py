"""Seed realistic demo fares and CPI series so the dashboard works before any live scrape."""
import random
from datetime import date, timedelta

from database import get_conn, init_db, insert_fare
from routes_config import ADVANCE_WINDOWS, CARRIER_NAMES, ROUTES


def _seed_fares(days: int = 60) -> int:
    today = date.today()
    carriers = list(CARRIER_NAMES.keys())
    base_fares = {
        ("DEL", "BOM"): 5200,
        ("DEL", "BLR"): 4800,
        ("BOM", "BLR"): 4500,
        ("DEL", "CCU"): 4700,
        ("BLR", "HYD"): 3600,
        ("MAA", "DEL"): 5100,
    }
    count = 0
    for i in range(days):
        scrape_date = today - timedelta(days=i)
        for origin, dest, weight in ROUTES:
            base = base_fares[(origin, dest)] * (1 + 0.02 * random.random() - 0.01)
            for adv in ADVANCE_WINDOWS:
                dep = scrape_date + timedelta(days=adv)
                carrier = random.choice(carriers)
                jitter = 1 + (random.random() * 0.25 - 0.10)
                total = round(base * jitter * (1 + adv * 0.003), 2)
                tax = round(total * 0.12, 2)
                base_fare = round(total - tax, 2)
                insert_fare({
                    "scrape_date": scrape_date.isoformat(),
                    "origin": origin,
                    "destination": dest,
                    "departure_date": dep.isoformat(),
                    "advance_days": adv,
                    "carrier": carrier,
                    "base_fare": base_fare,
                    "tax": tax,
                    "total_fare": total,
                    "source": "DemoSeed",
                    "scraped_at": scrape_date.isoformat(),
                })
                count += 1
    return count


def _seed_cpi(months: int = 12) -> int:
    today = date.today()
    cpi_base = 165.0
    rows = []
    for i in range(months - 1, -1, -1):
        month = (today.replace(day=1) - timedelta(days=i * 30)).strftime("%Y-%m")
        value = round(cpi_base + (months - i) * 0.8 + random.random() * 2 - 1, 2)
        rows.append((month, value, 5.2 + random.random() * 1.5, "DemoSeed"))

    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO cpi_series (month, cpi_index, yoy_change, source) VALUES (?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def seed_all() -> dict:
    init_db()
    fares = _seed_fares()
    cpi = _seed_cpi()
    return {"fares": fares, "cpi_points": cpi}


if __name__ == "__main__":
    print(seed_all())
