"""Airsight Streamlit MVP — National Airfare Price Index dashboard."""
import os
import sys
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

# Ensure project root is on path for cloud imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DB_PATH, ensure_tables, load_fares, row_count, scrape_dates
from index_calc import (
    advance_curve,
    carrier_table,
    compute_index_series,
    contribution_table,
    index_vs_cpi,
    route_breakdown_table,
)
from routes_config import ROUTES, route_label
from scraper import run_scrape_async
from seed_demo import seed_all

st.set_page_config(
    page_title="Airsight | National Airfare Price Index",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ACCENT = "#3B82F6"
FALL = "#EF4444"
RISE = "#22C55E"

st.markdown(
    """
    <style>
    .block-container { padding-top: 4.5rem !important; padding-bottom: 3rem !important; }
    header[data-testid="stHeader"] { background: transparent !important; }
    .eyebrow { margin: 0 0 .35rem 0 !important; color: #94a3b8; font-size: .85rem; letter-spacing: .04em; text-transform: uppercase; }
    h1 { font-size: clamp(1.7rem, 3.4vw, 2.9rem) !important; margin-bottom: .2rem !important; }
    h2 { font-size: clamp(1.2rem, 2.2vw, 1.7rem) !important; margin-top: 1.2rem !important; }
    [data-testid="stMetricValue"] { font-size: clamp(1.3rem, 2.2vw, 2rem) !important; }
    [data-testid="stMetricLabel"] { font-size: .8rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Init / seed ---
ensure_tables()
if row_count("fares") == 0:
    seed_all()

# --- Sidebar ---
st.sidebar.title("Airsight")
st.sidebar.markdown("National Airfare Price Index MVP")
page = st.sidebar.radio(
    "Navigate",
    ["Index dashboard", "Route explorer", "Data feed", "Methodology"],
)

scrape_dates_list = scrape_dates()
selected_date = st.sidebar.selectbox(
    "Scrape date",
    options=scrape_dates_list or [date.today().isoformat()],
    index=0,
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Run live scrape"):
    progress = st.sidebar.empty()

    async def _run():
        return await run_scrape_async(max_routes=6, progress_callback=lambda msg: progress.info(msg))

    import asyncio
    result = asyncio.run(_run())
    st.sidebar.success(f"Stored {result['stored']} fares")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(f"DB: `{DB_PATH}`")

# --- Helpers ---

def _index_card():
    idx = compute_index_series()
    if idx.empty:
        st.info("No fare data yet. Click **Run live scrape** or seed demo data.")
        return

    latest = idx.iloc[-1]
    prev = idx.iloc[-2] if len(idx) > 1 else latest
    change = latest["index"] - prev["index"] if prev["index"] else 0
    pct = (change / prev["index"] * 100) if prev["index"] else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest index", f"{latest['index']:.1f}", f"{pct:+.2f}%")
    c2.metric("Base date", latest["scrape_date"])
    c3.metric("Routes covered", int(latest["routes_covered"]))
    c4.metric("Fare records", row_count("fares"))

    chart = (
        alt.Chart(idx)
        .mark_line(color=ACCENT, point=True)
        .encode(
            x=alt.X("scrape_date:T", title="Scrape date"),
            y=alt.Y("index:Q", title="Index (base = earliest date = 100)", scale=alt.Scale(zero=False)),
            tooltip=["scrape_date", "index", "routes_covered"],
        )
        .properties(height=320)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def _route_explorer():
    breakdown = route_breakdown_table(selected_date)
    if breakdown.empty:
        st.info("No data for selected date.")
        return

    st.subheader(f"Route breakdown — {selected_date}")
    st.dataframe(
        breakdown.assign(avg_fare=lambda x: x["avg_fare"].round(0)).rename(
            columns={"avg_fare": "Avg fare (₹)", "samples": "Samples", "weight": "Weight"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    chart = (
        alt.Chart(breakdown)
        .mark_bar(color=ACCENT)
        .encode(
            x=alt.X("avg_fare:Q", title="Average fare (₹)"),
            y=alt.Y("route:N", sort="-x", title="Route"),
            tooltip=["route", "avg_fare", "samples"],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)

    contrib = contribution_table(selected_date)
    st.subheader("Contribution to index")
    st.dataframe(
        contrib[["route", "weight", "avg_fare", "contribution"]].rename(
            columns={"contribution": "Contribution"}
        ),
        use_container_width=True,
        hide_index=True,
    )


def _data_feed():
    st.subheader("Data feed")
    rows = load_fares(selected_date)
    if not rows:
        st.info("No rows for selected date.")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    carriers = carrier_table(selected_date)
    if not carriers.empty:
        with c1:
            st.markdown("**Carriers**")
            st.dataframe(carriers, use_container_width=True, hide_index=True)
    curve = advance_curve(selected_date)
    if not curve.empty:
        with c2:
            st.markdown("**Advance purchase curve**")
            chart = (
                alt.Chart(curve)
                .mark_line(color=RISE, point=True)
                .encode(
                    x=alt.X("advance_days:O", title="Days in advance"),
                    y=alt.Y("avg_fare:Q", title="Avg fare (₹)", scale=alt.Scale(zero=False)),
                    tooltip=["advance_days", "avg_fare", "samples"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, f"airsight_{selected_date}.csv", "text/csv")


def _methodology():
    st.subheader("Methodology")
    st.markdown(
        """
        **Airsight** is an MVP for SIH 2026 Statement 56: a national airfare price index built from
        real domestic fare observations.

        1. **Basket**: six city-pairs weighted by approximate DGCA traffic share.
        2. **Collection**: EaseMyTrip is scraped via Playwright (Firefox); ixigo/Google Travel are fallbacks.
        3. **Cleaning**: outlier removal (±2.5σ), keep lowest fare per carrier per route.
        4. **Index**: weighted Laspeyres-style relative, base = earliest scrape date = 100.
        5. **CPI overlay**: Consumer Price Index series for comparison (demo data in cloud).

        *Cloud note: live scraping may not run on Streamlit Community Cloud because Playwright/Firefox
        is unavailable there. Use the local version for live scraping; the cloud version shows
        dashboard, demo data, and CSV export.*
        """
    )


# --- Pages ---
if page == "Index dashboard":
    st.markdown("<p class='eyebrow'>Ministry of Statistics & Programme Implementation · CPI</p>", unsafe_allow_html=True)
    st.title("National Airfare Price Index")
    _index_card()

    st.subheader("Airfare index vs CPI")
    merged = index_vs_cpi()
    if not merged.empty and merged["cpi_index"].notna().any():
        base_air = merged["airfare_index"].dropna().iloc[0] or 1
        base_cpi = merged["cpi_index"].dropna().iloc[0] or 1
        plot_df = merged.copy()
        plot_df["airfare_index_norm"] = plot_df["airfare_index"] / base_air * 100
        plot_df["cpi_index_norm"] = plot_df["cpi_index"] / base_cpi * 100
        plot_df = plot_df.melt(
            id_vars=["month"],
            value_vars=["airfare_index_norm", "cpi_index_norm"],
            var_name="series",
            value_name="value",
        )
        plot_df["series"] = plot_df["series"].map(
            {"airfare_index_norm": "Airfare index", "cpi_index_norm": "CPI"}
        )
        chart = (
            alt.Chart(plot_df)
            .mark_line()
            .encode(
                x=alt.X("month:N", title="Month"),
                y=alt.Y("value:Q", title="Normalised index (base = 100)"),
                color=alt.Color("series:N", scale=alt.Scale(domain=["Airfare index", "CPI"], range=[ACCENT, FALL])),
                tooltip=["month", "series", "value"],
            )
            .properties(height=300)
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("CPI series not available.")

elif page == "Route explorer":
    st.title("Route explorer")
    _route_explorer()

elif page == "Data feed":
    st.title("Data feed")
    _data_feed()

elif page == "Methodology":
    st.title("Methodology")
    _methodology()
