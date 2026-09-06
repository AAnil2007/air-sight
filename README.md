# Airsight — Streamlit MVP

A simple public MVP for the SIH 2026 Statement 56 airfare price index prototype.

## Run locally

```bash
pip install -r requirements.txt
playwright install firefox
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

## Deploy publicly

See `DEPLOY.md` for step-by-step instructions to deploy on **Streamlit Community Cloud** and get a real shareable link.

## Notes

- Demo data is seeded automatically so the dashboard works immediately.
- Live scraping uses EaseMyTrip via Playwright (Firefox). It works locally; cloud free tiers usually do not support browsers.
