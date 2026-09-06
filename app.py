"""Airsight - National Airfare Price Index (SIH 2026, problem statement 56).

Streamlit prototype: EaseMyTrip fare scraping -> SQLite -> weighted
Laspeyres airfare price index, compared against MoSPI CPI series.

Run:  streamlit run app.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from database import init_db, row_count
from index_calc import (advance_curve, carrier_table, compute_index_series,
                        contribution_table, index_vs_cpi, load_cpi, load_fares,
                        route_breakdown_table)
from routes_config import ADVANCE_WINDOWS, ROUTE_WEIGHTS, route_label

st.set_page_config(page_title="Airsight | National Airfare Price Index",
                   page_icon="✈️", layout="wide")

ACCENT = "#3f8cff"
RISE = "#ff6b57"
FALL = "#37c98b"

st.markdown("""
<style>
  .block-container {padding-top: 4.5rem; padding-bottom: 3rem; max-width: 1250px;}
  header[data-testid="stHeader"] {background: transparent;}
  .eyebrow {text-transform: uppercase; letter-spacing: .14em; font-size: .72rem;
            color: #7b8794; font-weight: 600; margin: 0 0 .35rem 0;}
  .note {color: #7b8794; font-size: .82rem;}
  h1 {font-size: clamp(1.7rem, 3.4vw, 2.9rem); line-height: 1.15; margin-top: .1rem;}
  h2 {font-size: clamp(1.2rem, 2.2vw, 1.7rem);}
  [data-testid="stMetricValue"] {font-size: clamp(1.3rem, 2.2vw, 2rem);}
  [data-testid="stMetricLabel"] p {font-size: .8rem;}
</style>
""", unsafe_allow_html=True)

init_db()


@st.cache_data(ttl=60)
def _data():
    return load_fares(), load_cpi()


def rupee(value) -> str:
    return "—" if pd.isna(value) else f"₹{value:,.0f}"


fares, cpi = _data()

with st.sidebar:
    st.markdown('<p class="eyebrow">MoSPI · SIH26056</p>', unsafe_allow_html=True)
    st.title("Airsight")
    page = st.radio("View", ["Index dashboard", "Route explorer",
                             "Data feed", "Methodology"], label_visibility="collapsed")
    st.divider()
    st.caption(f"{row_count():,} fare observations stored")

    if st.button("Seed demo data", use_container_width=True):
        from seed_demo import seed_cpi, seed_fares
        with st.spinner("Seeding 60 days of demo fares…"):
            n = seed_fares()
            seed_cpi()
        _data.clear()
        st.success(f"Seeded {n:,} demo rows. Reloading…")
        st.rerun()

    scrape_scope = st.selectbox(
        "Live refresh scope",
        ["Quick · 6 searches", "Full · 30 searches"],
        help="Quick checks every route 7 days ahead. Full checks all five advance-purchase windows.",
    )
    if st.button("Run live scrape", use_container_width=True):
        progress_bar = st.progress(0, text="Starting live refresh…")
        status = st.empty()

        def show_progress(done: int, total: int, message: str) -> None:
            percent = int(done * 100 / total) if total else 0
            progress_bar.progress(percent, text=f"{done}/{total} searches")
            status.caption(message)

        try:
            from scraper import run_scrape
            selected_windows = [7] if scrape_scope.startswith("Quick") else ADVANCE_WINDOWS
            stored = run_scrape(windows=selected_windows, progress=show_progress)
            _data.clear()
            if stored:
                st.success(f"Stored {stored} live fare records.")
            else:
                st.warning("Refresh finished, but EaseMyTrip returned no usable fares. Try again later.")
        except Exception as exc:
            st.error(f"Scrape failed: {exc}")
        finally:
            progress_bar.empty()
            status.empty()
    st.caption("Quick refresh normally takes 1–4 minutes. Live scraping needs "
               "`playwright install firefox` to be run once.")

if fares.empty:
    st.title("National Airfare Price Index")
    st.warning("No fare data yet. Use **Seed demo data** in the sidebar to explore "
               "the dashboard, or **Run live scrape** to collect real EaseMyTrip fares.")
    st.stop()

index_df, base_date = compute_index_series(fares)
index_df = index_df.dropna(subset=["index"])
latest_date = index_df["scrape_date"].iloc[-1]
latest_index = float(index_df["index"].iloc[-1])
prev_index = float(index_df["index"].iloc[-2]) if len(index_df) > 1 else latest_index
latest_rows = fares[fares["scrape_date"] == latest_date]

# ---------------------------------------------------------------- dashboard
if page == "Index dashboard":
    st.markdown('<p class="eyebrow">Ministry of Statistics &amp; Programme '
                'Implementation · SIH26056</p>', unsafe_allow_html=True)
    st.title("National Airfare Price Index")
    st.caption(f"Weighted airfare index for a six-route domestic basket. "
               f"Base period {base_date} = 100. Latest reading {latest_date}.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Index level", f"{latest_index:.2f}",
              f"{latest_index - prev_index:+.2f} vs previous day")
    c2.metric("Change since base", f"{latest_index - 100:+.2f} pts")
    c3.metric("Average fare (latest)", rupee(latest_rows["total_fare"].mean()))
    tax_share = latest_rows["taxes"].sum() / latest_rows["total_fare"].sum() * 100
    c4.metric("Taxes as share of fare", f"{tax_share:.1f}%")

    st.subheader("Index over time")
    line = index_df.copy()
    chart = alt.Chart(line).mark_line(color=ACCENT, point=False).encode(
        x=alt.X("scrape_date:T", title="Observation date"),
        y=alt.Y("index:Q", title="Index (base = 100)",
                scale=alt.Scale(zero=False)),
        tooltip=["scrape_date", "index", "routes_covered"],
    ).properties(height=300)
    baseline = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(
        strokeDash=[5, 5], color="#94a3b8").encode(y="y:Q")
    st.altair_chart(chart + baseline, use_container_width=True)

    st.subheader("Airfare index vs MoSPI CPI")
    comparison = index_vs_cpi(index_df, cpi)
    if comparison.empty or comparison["APIx"].isna().all():
        st.info("CPI comparison needs at least one full month of index data "
                "plus CPI rows. Seed demo data to see it.")
    else:
        rebased = comparison.dropna(subset=["APIx"]).copy()
        for col in ["APIx", "CPI (General)", "CPI (Transport)"]:
            first = rebased[col].dropna().iloc[0]
            rebased[col] = (rebased[col] / first * 100).round(2)
        melted = rebased.melt("month", ["APIx", "CPI (General)", "CPI (Transport)"],
                              var_name="Series", value_name="Rebased (=100)")
        st.altair_chart(
            alt.Chart(melted).mark_line(point=True).encode(
                x=alt.X("month:N", title="Month"),
                y=alt.Y("Rebased (=100):Q", scale=alt.Scale(zero=False)),
                color=alt.Color("Series:N", scale=alt.Scale(
                    range=[ACCENT, "#f4b740", "#8b5cf6"])),
                tooltip=["month", "Series", "Rebased (=100)"],
            ).properties(height=300),
            use_container_width=True)
        st.markdown('<p class="note">All three series rebased to 100 at the first '
                    'common month so relative movement is comparable.</p>',
                    unsafe_allow_html=True)

    st.subheader("Route contribution to the index move")
    contrib = contribution_table(fares, base_date, latest_date)
    if contrib.empty:
        st.info("Not enough overlapping route data yet.")
    else:
        st.altair_chart(
            alt.Chart(contrib).mark_bar().encode(
                x=alt.X("Contribution (pts):Q", title="Weighted points"),
                y=alt.Y("Route:N", sort="-x", title=None),
                color=alt.condition(alt.datum["Contribution (pts)"] > 0,
                                    alt.value(RISE), alt.value(FALL)),
                tooltip=["Route", "Weight %", "Index", "Contribution (pts)"],
            ).properties(height=240),
            use_container_width=True)

    st.subheader("Route basket")
    st.dataframe(route_breakdown_table(fares, base_date, latest_date),
                 use_container_width=True, hide_index=True)

# ----------------------------------------------------------- route explorer
elif page == "Route explorer":
    st.markdown('<p class="eyebrow">Route level detail</p>', unsafe_allow_html=True)
    st.title("Route explorer")

    labels = {route_label(r): r for r in ROUTE_WEIGHTS}
    choice = st.selectbox("Route", list(labels))
    route = labels[choice]
    windows = st.multiselect("Advance-purchase windows (days before departure)",
                             ADVANCE_WINDOWS, default=ADVANCE_WINDOWS)

    subset = fares[(fares["origin"] == route[0]) & (fares["dest"] == route[1])]
    if windows:
        subset = subset[subset["advance_days"].isin(windows)]

    if subset.empty:
        st.warning("No observations for this route and window selection.")
        st.stop()

    daily = (subset.groupby("scrape_date")[["base_fare", "taxes", "total_fare"]]
             .mean().round(2).reset_index())
    latest = daily.iloc[-1]
    first = daily.iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latest average fare", rupee(latest["total_fare"]),
              f"{(latest['total_fare'] / first['total_fare'] - 1) * 100:+.1f}% since {first['scrape_date']}")
    m2.metric("Base fare", rupee(latest["base_fare"]))
    m3.metric("Taxes & charges", rupee(latest["taxes"]))
    m4.metric("Basket weight", f"{ROUTE_WEIGHTS[route] * 100:.0f}%")

    st.subheader("Average daily fare")
    st.altair_chart(
        alt.Chart(daily).mark_line(point=True, color=ACCENT).encode(
            x=alt.X("scrape_date:T", title="Observation date"),
            y=alt.Y("total_fare:Q", title="Average total fare (₹)",
                    scale=alt.Scale(zero=False)),
            tooltip=["scrape_date", "base_fare", "taxes", "total_fare"],
        ).properties(height=300),
        use_container_width=True)

    st.subheader("Base fare vs taxes")
    stacked = daily.melt("scrape_date", ["base_fare", "taxes"],
                         var_name="Component", value_name="₹")
    st.altair_chart(
        alt.Chart(stacked).mark_bar().encode(
            x=alt.X("scrape_date:T", title=None),
            y=alt.Y("₹:Q", stack="zero"),
            color=alt.Color("Component:N", scale=alt.Scale(range=[ACCENT, "#f97359"])),
            tooltip=["scrape_date", "Component", "₹"],
        ).properties(height=260),
        use_container_width=True)

    st.subheader("Airline comparison (latest observation date)")
    st.dataframe(carrier_table(subset, latest_date), use_container_width=True,
                 hide_index=True)

    st.subheader("Fare vs days before departure")
    curve = advance_curve(subset, latest_date)
    if curve.empty:
        st.info("No latest-date observations for this route.")
    else:
        st.altair_chart(
            alt.Chart(curve).mark_line(point=True, color="#f4b740").encode(
                x=alt.X("Days before departure:Q"),
                y=alt.Y("Avg total fare:Q", scale=alt.Scale(zero=False)),
                tooltip=["Days before departure", "Avg total fare"],
            ).properties(height=250),
            use_container_width=True)

# ---------------------------------------------------------------- data feed
elif page == "Data feed":
    st.markdown('<p class="eyebrow">Provenance &amp; coverage</p>', unsafe_allow_html=True)
    st.title("Data feed")

    d1, d2, d3 = st.columns(3)
    d1.metric("Observations stored", f"{len(fares):,}")
    d2.metric("Observation dates", f"{fares['scrape_date'].nunique()}")
    d3.metric("Routes covered", f"{fares.groupby(['origin', 'dest']).ngroups}")

    st.subheader("Records by source")
    st.dataframe(fares.groupby("source").size().reset_index(name="Records"),
                 use_container_width=True, hide_index=True)

    st.subheader("Coverage by observation date")
    coverage = (fares.groupby("scrape_date")
                .agg(Records=("total_fare", "size"),
                     Routes=("origin", "nunique"),
                     Airlines=("carrier_name", "nunique"))
                .reset_index().sort_values("scrape_date", ascending=False))
    st.dataframe(coverage, use_container_width=True, hide_index=True)

    st.subheader("Latest observations")
    st.dataframe(fares.sort_values("scrape_date", ascending=False).head(200),
                 use_container_width=True, hide_index=True)

    st.download_button("Download all observations (CSV)",
                       fares.to_csv(index=False).encode(),
                       file_name="airsight_fare_observations.csv",
                       mime="text/csv")
    st.download_button("Download index series (CSV)",
                       index_df.to_csv(index=False).encode(),
                       file_name="airsight_index_series.csv",
                       mime="text/csv")

# -------------------------------------------------------------- methodology
else:
    st.markdown('<p class="eyebrow">SIH 2026 · Problem statement 56</p>',
                unsafe_allow_html=True)
    st.title("Methodology")

    st.markdown(f"""
### Objective
Build a transparent, reproducible **Airfare Price Index (APIx)** for Indian
domestic aviation from publicly observable fares, in the spirit of the MoSPI
Consumer Price Index.

### Collection
- Source: **EaseMyTrip** flight-listing JSON, captured with Playwright.
- Basket: **{len(ROUTE_WEIGHTS)} trunk routes**, weighted by domestic traffic share.
- Advance-purchase windows: **{', '.join(str(w) for w in ADVANCE_WINDOWS)} days** before departure.
- Only **non-stop** economy itineraries are kept.
- **Base fare and taxes are stored separately**, so the tax component is visible.
- Fares more than **2.5 standard deviations** from the batch mean are dropped as outliers.

### Index formula
For each route *r* with weight *w<sub>r</sub>*, the price relative is the ratio of the
current-period average total fare to the base-period average:

$$ APIx_t = 100 \\times \\frac{{\\sum_r w_r \\cdot (P_{{r,t}} / P_{{r,0}})}}{{\\sum_r w_r}} $$

Weights are renormalised over routes that have data in **both** periods, so a
temporarily missing route cannot distort the level. Base period: **{base_date} = 100**.

### CPI comparison
CPI (General) and CPI (Transport & Communication) are stored monthly. On the
dashboard the airfare index and both CPI series are rebased to 100 at the
first common month, so relative movement is directly comparable.

### Storage
SQLite (`airfares.db`): `fares` holds one row per airline / fare brand /
travel date / observation date; `cpi_series` holds the monthly CPI reference.

### Limitations
- Advertised lowest fares, not transacted fares — no booking-volume weighting.
- A single online travel agency; multi-source triangulation is future work.
- Demo-seeded rows are tagged `source = DemoSeed` and are for interface
  demonstration only.
""")

st.divider()
st.markdown('<p class="note">Airsight · prototype for Smart India Hackathon 2026 '
            'problem statement SIH26056 (MoSPI). Not an official statistic.</p>',
            unsafe_allow_html=True)
