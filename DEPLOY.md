# Deploy Airsight Streamlit MVP to a public link

The easiest free way to get a real shareable URL is **Streamlit Community Cloud**.

## Important cloud limitation

Live EaseMyTrip scraping uses Playwright + Firefox. Streamlit Community Cloud does **not** support browsers, so the **Run live scrape** button will not work there. The public link will still show:

- Index dashboard with demo data
- Route explorer, data feed, CSV export
- CPI comparison chart

Keep this local version on your computer for real live scraping.

## Step 1: upload to GitHub

1. Create a new empty GitHub repository (e.g. `airsight-mvp`).
2. Upload **all files in this folder** to the repo root:
   - `app.py`
   - `database.py`
   - `index_calc.py`
   - `parser.py`
   - `routes_config.py`
   - `scraper.py`
   - `seed_demo.py`
   - `requirements.txt`
   - `DEPLOY.md`
   - `README.md`
   - `data/` folder (can be empty)

You can use the GitHub web upload, GitHub Desktop, or the git CLI.

## Step 2: deploy on Streamlit Community Cloud

1. Go to https://streamlit.io/cloud and sign in with your GitHub account.
2. Click **New app → From GitHub**.
3. Pick your repository and branch (`main`).
4. Set **Main file path** to `app.py`.
5. Click **Deploy**.

Streamlit will install packages from `requirements.txt` and start the app. After a minute or two you will get a public URL like:

```
https://airsight-mvp-yourname.streamlit.app
```

That is your MVP link — you can share it with anyone.

## Optional: custom subdomain

In Streamlit Cloud, open the app settings and pick a custom subdomain such as `airsight-anil` if it is available.

## If the app fails to start

- Check the **Manage app** logs in Streamlit Cloud.
- Make sure `requirements.txt` is at the repo root.
- Make sure `app.py` is at the repo root and imports are relative (they are).
- If Playwright errors appear, ignore them — live scraping is disabled in the cloud by default.
