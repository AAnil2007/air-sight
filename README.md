# Airsight — Streamlit version

National Airfare Price Index prototype for **Smart India Hackathon 2026,
problem statement 56 (MoSPI)**. Scrapes real EaseMyTrip fares, stores them in
SQLite, and publishes a weighted Laspeyres airfare index compared with CPI.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install firefox                              # only needed for live scraping
streamlit run app.py
```

The app opens at http://localhost:8501.

- First run has no data. Click **Seed demo data** in the sidebar to load 60 days
  of clearly-labelled demo fares plus 12 CPI months, so every chart works.
- Click **Run live scrape** to collect real EaseMyTrip fares. **Quick** is the default
  and visits 6 routes at one advance window (normally 1–4 minutes). **Full** visits
  6 routes × 5 windows and can take considerably longer. The app shows each search
  as it runs and applies a strict timeout if EaseMyTrip does not respond.
- Running `python scraper.py` from a terminal performs the full 30-search refresh.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit UI: index dashboard, route explorer, data feed, methodology |
| `index_calc.py` | All index maths — weighted index series, route breakdown, contributions, CPI alignment |
| `scraper.py` | Playwright capture of EaseMyTrip fare JSON, then parse + store |
| `parser.py` | Extracts non-stop fares with base/tax split, drops outliers |
| `database.py` | SQLite schema (`fares`, `cpi_series`) and inserts |
| `routes_config.py` | Route basket, weights, advance windows, airline codes |
| `seed_demo.py` | Demo fares + CPI months (tagged `source = DemoSeed`) |

## Index formula

```
APIx_t = 100 * Σ(w_r * P_r,t / P_r,0) / Σ(w_r)
```

Weights renormalise over routes present in both the base and current period,
so a missing route cannot distort the level. Base period = first observation
date, set to 100.

## Compliance notes for the problem statement

- Base fare and taxes stored and displayed separately.
- Non-stop itineraries only.
- Outlier fares removed (2.5σ within each scrape batch).
- Multiple advance-purchase windows (1, 7, 15, 30, 45 days).
- Traffic-share route weighting, transparent methodology page.
- CSV export of both raw observations and the index series.
