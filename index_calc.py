"""Weighted Laspeyres-style airfare index and analytics helpers."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from database import get_conn, load_cpi, load_fares
from routes_config import ROUTES, route_label


def _route_weight(origin: str, dest: str) -> float:
    for o, d, w in ROUTES:
        if (o == origin and d == dest) or (o == dest and d == origin):
            return w
    return 0.0


def route_avg_fares(scrape_date: Optional[str] = None) -> pd.DataFrame:
    rows = load_fares(scrape_date)
    if not rows:
        return pd.DataFrame(columns=["route", "weight", "avg_fare", "samples"])

    df = pd.DataFrame([dict(r) for r in rows])
    grouped = df.groupby(["origin", "destination"]).agg(
        avg_fare=("total_fare", "mean"),
        samples=("total_fare", "count"),
    ).reset_index()
    grouped["route"] = grouped.apply(lambda r: route_label(r["origin"], r["destination"]), axis=1)
    grouped["weight"] = grouped.apply(lambda r: _route_weight(r["origin"], r["destination"]), axis=1)
    return grouped[["route", "weight", "avg_fare", "samples"]]


def compute_index_series() -> pd.DataFrame:
    """Return one row per scrape_date: index value and routes covered."""
    rows = load_fares()
    if not rows:
        return pd.DataFrame(columns=["scrape_date", "index", "routes_covered"])

    df = pd.DataFrame([dict(r) for r in rows])
    # attach weights
    df["weight"] = df.apply(lambda r: _route_weight(r["origin"], r["destination"]), axis=1)

    # route-level average per scrape_date
    route_avg = df.groupby(["scrape_date", "origin", "destination"]).agg(
        avg_fare=("total_fare", "mean"),
        weight=("weight", "first"),
    ).reset_index()

    # base period = earliest scrape_date
    base_date = route_avg["scrape_date"].min()
    base = route_avg[route_avg["scrape_date"] == base_date].set_index(["origin", "destination"])["avg_fare"]

    indices = []
    for sd, group in route_avg.groupby("scrape_date"):
        weighted_sum = 0.0
        weight_sum = 0.0
        for _, r in group.iterrows():
            key = (r["origin"], r["destination"])
            if key in base and base[key] > 0:
                relative = r["avg_fare"] / base[key]
                weighted_sum += relative * r["weight"]
                weight_sum += r["weight"]
        idx = (weighted_sum / weight_sum * 100) if weight_sum > 0 else None
        indices.append({
            "scrape_date": sd,
            "index": round(idx, 2) if idx else None,
            "routes_covered": len(group),
        })

    return pd.DataFrame(indices).sort_values("scrape_date")


def route_breakdown_table(scrape_date: Optional[str] = None) -> pd.DataFrame:
    return route_avg_fares(scrape_date)


def contribution_table(scrape_date: Optional[str] = None) -> pd.DataFrame:
    avg = route_avg_fares(scrape_date)
    if avg.empty:
        return avg
    avg["contribution"] = (avg["weight"] * avg["avg_fare"] / (avg["avg_fare"].mean() or 1)).round(2)
    return avg


def carrier_table(scrape_date: Optional[str] = None) -> pd.DataFrame:
    rows = load_fares(scrape_date)
    if not rows:
        return pd.DataFrame(columns=["carrier", "avg_fare", "samples", "share_pct"])
    df = pd.DataFrame([dict(r) for r in rows])
    grouped = df.groupby("carrier").agg(avg_fare=("total_fare", "mean"), samples=("total_fare", "count")).reset_index()
    grouped["share_pct"] = (grouped["samples"] / grouped["samples"].sum() * 100).round(1)
    return grouped.sort_values("avg_fare")


def advance_curve(scrape_date: Optional[str] = None) -> pd.DataFrame:
    rows = load_fares(scrape_date)
    if not rows:
        return pd.DataFrame(columns=["advance_days", "avg_fare", "samples"])
    df = pd.DataFrame([dict(r) for r in rows])
    return df.groupby("advance_days").agg(avg_fare=("total_fare", "mean"), samples=("total_fare", "count")).reset_index().sort_values("advance_days")


def index_vs_cpi() -> pd.DataFrame:
    idx = compute_index_series()
    cpi = pd.DataFrame([dict(r) for r in load_cpi()])
    if idx.empty or cpi.empty:
        return pd.DataFrame(columns=["month", "airfare_index", "cpi_index"])
    idx["month"] = pd.to_datetime(idx["scrape_date"]).dt.to_period("M").astype(str)
    cpi["month"] = cpi["month"].astype(str)
    monthly = idx.groupby("month")["index"].mean().reset_index().rename(columns={"index": "airfare_index"})
    merged = monthly.merge(cpi[["month", "cpi_index"]], on="month", how="outer").sort_values("month")
    return merged
