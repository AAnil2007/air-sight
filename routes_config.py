"""Route basket, weights and advance-purchase windows.

Weights approximate DGCA domestic passenger traffic share on these trunk
routes and are normalised to sum to 1.0. Keep every module importing from
here so the basket is defined exactly once.
"""

ROUTE_WEIGHTS = {
    ("DEL", "BOM"): 0.25,
    ("DEL", "BLR"): 0.20,
    ("BOM", "BLR"): 0.15,
    ("DEL", "CCU"): 0.15,
    ("BLR", "HYD"): 0.15,
    ("MAA", "DEL"): 0.10,
}

ROUTE_NAMES = {
    ("DEL", "BOM"): "Delhi to Mumbai",
    ("DEL", "BLR"): "Delhi to Bengaluru",
    ("BOM", "BLR"): "Mumbai to Bengaluru",
    ("DEL", "CCU"): "Delhi to Kolkata",
    ("BLR", "HYD"): "Bengaluru to Hyderabad",
    ("MAA", "DEL"): "Chennai to Delhi",
}

ROUTES = list(ROUTE_WEIGHTS.keys())

# Days ahead of departure that the scraper samples (advance-purchase windows).
ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

CARRIER_NAMES = {
    "6E": "IndiGo",
    "IX": "Air India Express",
    "QP": "Akasa Air",
    "AI": "Air India",
    "SG": "SpiceJet",
    "UK": "Vistara",
    "S5": "Star Air",
}


def route_label(route: tuple[str, str]) -> str:
    return ROUTE_NAMES.get(route, f"{route[0]}-{route[1]}")
