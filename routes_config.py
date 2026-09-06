"""Shared route basket and carrier configuration."""
from typing import List, Tuple

# SIH 2026 Statement 56 style basket: top domestic city-pairs by DGCA traffic weights
ROUTES: List[Tuple[str, str, float]] = [
    ("DEL", "BOM", 0.25),
    ("DEL", "BLR", 0.20),
    ("BOM", "BLR", 0.15),
    ("DEL", "CCU", 0.15),
    ("BLR", "HYD", 0.15),
    ("MAA", "DEL", 0.10),
]

ROUTE_NAMES = {
    ("DEL", "BOM"): "Delhi ↔ Mumbai",
    ("DEL", "BLR"): "Delhi ↔ Bangalore",
    ("BOM", "BLR"): "Mumbai ↔ Bangalore",
    ("DEL", "CCU"): "Delhi ↔ Kolkata",
    ("BLR", "HYD"): "Bangalore ↔ Hyderabad",
    ("MAA", "DEL"): "Chennai ↔ Delhi",
}

CITY_NAMES = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bangalore",
    "HYD": "Hyderabad",
    "CCU": "Kolkata",
    "MAA": "Chennai",
    "GOI": "Goa",
    "AMD": "Ahmedabad",
    "PNQ": "Pune",
    "GAU": "Guwahati",
    "SXR": "Srinagar",
    "JAI": "Jaipur",
}

CARRIER_NAMES = {
    "6E": "IndiGo",
    "IX": "Air India Express",
    "QP": "Akasa Air",
    "AI": "Air India",
    "SG": "SpiceJet",
    "UK": "Vistara",
    "S5": "Star Air",
}

CARRIER_ALIASES = {
    "indigo": "6E",
    "indigo airlines": "6E",
    "go first": "G8",
    "gofirst": "G8",
    "air india": "AI",
    "airindia": "AI",
    "air india express": "IX",
    "airindiaexpress": "IX",
    "aix connect": "IX",
    "akasa air": "QP",
    "akasa": "QP",
    "spicejet": "SG",
    "spice jet": "SG",
    "vistara": "UK",
    "star air": "S5",
}

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]


def route_label(origin: str, dest: str) -> str:
    return ROUTE_NAMES.get((origin, dest), f"{CITY_NAMES.get(origin, origin)} ↔ {CITY_NAMES.get(dest, dest)}")


def normalise_carrier(name: str) -> str:
    """Map scraped/free-text carrier names to IATA code."""
    key = name.lower().strip()
    # longest alias first so "air india express" beats "air india"
    for alias, code in sorted(CARRIER_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in key or key in alias:
            return code
    # try first token if it looks like a 2-char code
    token = key.split()[0] if key else ""
    if len(token) == 2 and token.upper() in CARRIER_NAMES:
        return token.upper()
    return name[:2].upper()
