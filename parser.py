"""Parses the EaseMyTrip AirBus_New JSON payload into fare records."""
import json

from routes_config import CARRIER_NAMES


def extract_carrier_code(option: dict, valid_codes: set) -> str | None:
    """Carrier code sits inside the backtick-delimited BkKY string; its
    position shifts, so match against codes the payload itself declares."""
    try:
        bkky_str = option["b"][0]["BkKY"][0]
        for part in bkky_str.split("`"):
            if part in valid_codes:
                return part
    except (KeyError, IndexError):
        pass
    return None


def is_nonstop(option: dict) -> bool:
    """SD looks like 'Non-Stop|6529|9|DEL-BOM||' or '1-Stop|...'."""
    return option.get("SD", "").startswith("Non-Stop")


def remove_outliers(records: list[dict], z_thresh: float = 2.5) -> list[dict]:
    """Drop statistically extreme fares within a batch (MoSPI requirement)."""
    fares = [r["total_fare"] for r in records if r["total_fare"] is not None]
    if len(fares) < 3:
        return records

    mean = sum(fares) / len(fares)
    variance = sum((f - mean) ** 2 for f in fares) / len(fares)
    std = variance ** 0.5 or 1

    return [
        r for r in records
        if r["total_fare"] is not None
        and abs((r["total_fare"] - mean) / std) <= z_thresh
    ]


def parse_easemytrip(raw_json: dict, origin: str, dest: str,
                     travel_date: str, advance_days: int,
                     scrape_date: str, source: str = "EaseMyTrip") -> list[dict]:
    """Non-stop fares with base fare / tax split, outliers removed."""
    valid_codes = set(raw_json.get("m", {}).keys())
    options = raw_json.get("j", [{}])[0].get("s", [])

    records = []
    for option in options:
        if not is_nonstop(option):
            continue

        carrier_code = extract_carrier_code(option, valid_codes)
        if not carrier_code:
            continue

        for fare_brand in option.get("lstFr", []):
            base_fare = fare_brand.get("BF")
            total_fare = fare_brand.get("TF")
            if base_fare is None or total_fare is None:
                continue

            records.append({
                "origin": origin,
                "dest": dest,
                "carrier_code": carrier_code,
                "carrier_name": CARRIER_NAMES.get(carrier_code, carrier_code),
                "scrape_date": scrape_date,
                "travel_date": travel_date,
                "advance_days": advance_days,
                "fare_class": fare_brand.get("FN"),
                "base_fare": base_fare,
                "taxes": round(total_fare - base_fare, 2),
                "total_fare": total_fare,
                "stops": 0,
                "source": source,
            })

    return remove_outliers(records)


if __name__ == "__main__":
    from pathlib import Path

    files = sorted(Path("data/raw").glob("*_AirBus_New_*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("No AirBus_New files in data/raw/")
    else:
        latest = files[0]
        origin, dest, travel_date_str = latest.stem.split("_")[:3]
        with open(latest, encoding="utf-8") as f:
            raw = json.load(f)
        recs = parse_easemytrip(raw, origin, dest,
                                travel_date_str.replace("-", "/"),
                                advance_days=1, scrape_date="1970-01-01")
        print(f"{len(recs)} non-stop records after outlier removal")
