"""Airfare Price Index (APIx) computation - weighted Laspeyres, base = 100.

All index math lives here so the Streamlit app stays presentation-only.
"""
import pandas as pd

from database import get_conn
from routes_config import ROUTE_WEIGHTS, route_label


def load_fares() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM fares", conn)
    except Exception:
        df = pd.DataFrame(columns=[
            "origin", "dest", "carrier_code", "carrier_name", "scrape_date",
            "travel_date", "advance_days", "fare_class", "base_fare",
            "taxes", "total_fare", "stops", "source",
        ])
    finally:
        conn.close()
    return df


def load_cpi() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM cpi_series ORDER BY month", conn)
    except Exception:
        df = pd.DataFrame(columns=["month", "cpi_general", "cpi_transport"])
    finally:
        conn.close()
    return df


def route_avg_fares(df: pd.DataFrame, scrape_date: str) -> pd.Series:
    subset = df[df["scrape_date"] == scrape_date]
    return subset.groupby(["origin", "dest"])["total_fare"].mean()


def route_avg_details(df: pd.DataFrame, scrape_date: str) -> pd.DataFrame:
    subset = df[df["scrape_date"] == scrape_date]
    return subset.groupby(["origin", "dest"])[["base_fare", "taxes", "total_fare"]].mean()


def compute_index_series(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """{scrape_date, index, routes_covered} plus the base date used."""
    dates = sorted(df["scrape_date"].dropna().unique())
    if not dates:
        return pd.DataFrame(columns=["scrape_date", "index", "routes_covered"]), None

    base_date = dates[0]
    base_avg = route_avg_fares(df, base_date)

    records = []
    for d in dates:
        current_avg = route_avg_fares(df, d)
        weighted_sum, weight_total, covered = 0.0, 0.0, 0

        for route, weight in ROUTE_WEIGHTS.items():
            if route in base_avg.index and route in current_avg.index:
                weighted_sum += weight * (current_avg[route] / base_avg[route])
                weight_total += weight
                covered += 1

        records.append({
            "scrape_date": d,
            "index": round((weighted_sum / weight_total) * 100, 2) if weight_total else None,
            "routes_covered": covered,
        })

    return pd.DataFrame(records), base_date


def route_breakdown_table(df: pd.DataFrame, base_date: str, latest_date: str) -> pd.DataFrame:
    base_period_avg = route_avg_fares(df, base_date)
    current_period_avg = route_avg_fares(df, latest_date)
    current_details = route_avg_details(df, latest_date)

    rows = []
    for route, weight in ROUTE_WEIGHTS.items():
        base_fare_period = base_period_avg.get(route)
        current_fare_period = current_period_avg.get(route)
        route_index = (
            round(current_fare_period / base_fare_period * 100, 2)
            if base_fare_period and current_fare_period else None
        )
        detail = current_details.loc[route] if route in current_details.index else None

        rows.append({
            "Route": route_label(route),
            "Code": f"{route[0]}-{route[1]}",
            "Weight %": round(weight * 100, 1),
            "Base Fare": round(detail["base_fare"], 2) if detail is not None else None,
            "Taxes": round(detail["taxes"], 2) if detail is not None else None,
            "Total Fare": round(detail["total_fare"], 2) if detail is not None else None,
            "Fare at Base Date": round(base_fare_period, 2) if base_fare_period else None,
            "Index": route_index,
        })

    return pd.DataFrame(rows)


def contribution_table(df: pd.DataFrame, base_date: str, latest_date: str) -> pd.DataFrame:
    """Each route's weighted points contributed to the headline index move."""
    table = route_breakdown_table(df, base_date, latest_date).dropna(subset=["Index"])
    if table.empty:
        return table
    table = table.copy()
    table["Contribution (pts)"] = (
        (table["Index"] - 100) * table["Weight %"] / 100
    ).round(2)
    return table.sort_values("Contribution (pts)", ascending=False)


def carrier_table(df: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    subset = df[df["scrape_date"] == latest_date]
    if subset.empty:
        return pd.DataFrame()
    out = (subset.groupby("carrier_name")
           .agg(**{"Observations": ("total_fare", "size"),
                   "Avg Base Fare": ("base_fare", "mean"),
                   "Avg Taxes": ("taxes", "mean"),
                   "Avg Total Fare": ("total_fare", "mean")})
           .round(2).reset_index()
           .rename(columns={"carrier_name": "Airline"}))
    return out.sort_values("Avg Total Fare")


def advance_curve(df: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    subset = df[df["scrape_date"] == latest_date]
    if subset.empty:
        return pd.DataFrame()
    return (subset.groupby("advance_days")["total_fare"].mean()
            .round(2).reset_index()
            .rename(columns={"advance_days": "Days before departure",
                             "total_fare": "Avg total fare"}))


def index_vs_cpi(index_df: pd.DataFrame, cpi_df: pd.DataFrame) -> pd.DataFrame:
    """Monthly average APIx aligned with CPI general and transport series."""
    if index_df.empty or cpi_df.empty:
        return pd.DataFrame()
    idx = index_df.dropna(subset=["index"]).copy()
    idx["month"] = idx["scrape_date"].str.slice(0, 7)
    monthly = idx.groupby("month")["index"].mean().round(2).reset_index()
    merged = cpi_df.merge(monthly, on="month", how="left")
    return merged.rename(columns={"index": "APIx",
                                  "cpi_general": "CPI (General)",
                                  "cpi_transport": "CPI (Transport)"})
