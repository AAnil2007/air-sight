"""Parse EaseMyTrip AirBus_New_*.json payloads into structured fares."""
import json
import math
from datetime import datetime
from typing import Any, Dict, List

from routes_config import normalise_carrier


def _fare_sort_key(f: Dict[str, Any]) -> float:
    return f.get("total_fare", float("inf"))


def parse_emt_payload(payload: Any, origin: str, dest: str, scrape_date: str, departure_date: str) -> List[Dict[str, Any]]:
    """Extract non-stop one-way fares from EaseMyTrip response structure."""
    rows: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return rows

    data = payload.get("d", payload)
    flights = data.get("flights", [])
    if not isinstance(flights, list):
        return rows

    for seg in flights:
        if not isinstance(seg, dict):
            continue
        # only non-stop segments
        if seg.get("stops", 0) not in (0, "0", None):
            continue
        airline = seg.get("airline", "")
        if not airline:
            continue
        carrier = normalise_carrier(airline)

        # fare object may be nested
        fare = seg.get("fare", {}) or {}
        if not fare:
            fare = seg
        base = float(fare.get("base", 0) or fare.get("baseFare", 0) or 0)
        tax = float(fare.get("tax", 0) or fare.get("taxes", 0) or 0)
        total = float(fare.get("total", 0) or fare.get("totalFare", 0) or 0)
        if total <= 0 and base > 0:
            total = base + tax
        if total <= 0:
            continue

        advance = (datetime.strptime(departure_date, "%Y-%m-%d").date() -
                   datetime.strptime(scrape_date, "%Y-%m-%d").date()).days

        rows.append({
            "scrape_date": scrape_date,
            "origin": origin,
            "destination": dest,
            "departure_date": departure_date,
            "advance_days": advance,
            "carrier": carrier,
            "base_fare": round(base, 2),
            "tax": round(tax, 2),
            "total_fare": round(total, 2),
            "source": "live",
            "scraped_at": datetime.utcnow().isoformat(),
        })

    # keep lowest fare per carrier per direction
    by_carrier: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        code = r["carrier"]
        if code not in by_carrier or r["total_fare"] < by_carrier[code]["total_fare"]:
            by_carrier[code] = r
    return list(by_carrier.values())


def remove_outliers(rows: List[Dict[str, Any]], sigma: float = 2.5) -> List[Dict[str, Any]]:
    if len(rows) < 4:
        return rows
    totals = [r["total_fare"] for r in rows]
    mean = sum(totals) / len(totals)
    std = math.sqrt(sum((x - mean) ** 2 for x in totals) / len(totals)) or 1
    return [r for r in rows if abs(r["total_fare"] - mean) <= sigma * std]
