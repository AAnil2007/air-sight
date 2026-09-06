"""Playwright scraper: captures EaseMyTrip fare JSON for the route basket."""
import json
import random
import re
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright

import database
from database import init_db, insert_fares
from parser import parse_easemytrip
from routes_config import ADVANCE_WINDOWS, ROUTES

def _raw_dir() -> Path:
    """Writable folder for captured JSON, next to the database file.

    Some Windows setups (OneDrive-synced folders, non-ASCII paths) refuse
    directory creation next to the script, so we fall back to a temp folder.
    """
    for base in (database.DB_PATH.parent, Path(tempfile.gettempdir()) / "airsight"):
        try:
            target = base / "data" / "raw"
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            continue
    raise OSError("Could not create a folder for scraped data")


RAW_DIR = Path(tempfile.gettempdir()) / "airsight" / "data" / "raw"
IGNORE_SUBSTRINGS = ["moengage", "GetCoupons", "CheckSignIn", "UMS", "PSP", "google.com"]


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-_.]", "_", name)[:50]


def build_url(origin: str, dest: str, travel_date: str) -> str:
    return (
        f"https://www.easemytrip.com/flight-search/listing?"
        f"srch={origin}-{origin}-India%7C{dest}-{dest}-India%7C{travel_date}"
        f"&px=1-0-0&cbn=0&ar=undefined&isow=true&isdm=true&lang=en-us"
        f"&IsDoubleSeat=false&CCODE=IN&curr=INR&apptype=B2C"
    )


def make_response_handler(origin, dest, travel_date, scrape_ts):
    safe_date = travel_date.replace("/", "-")

    def handle_response(response):
        if any(s in response.url for s in IGNORE_SUBSTRINGS):
            return
        if "application/json" not in response.headers.get("content-type", ""):
            return
        try:
            data = response.json()
            endpoint = sanitize_filename(response.url.split("?")[0].split("/")[-1] or "data")
            path = RAW_DIR / f"{origin}_{dest}_{safe_date}_{endpoint}_{scrape_ts}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  [saved] {path.name}")
        except Exception as exc:
            print(f"  [skip] {response.url}: {exc}")

    return handle_response


def scrape_route(browser, origin: str, dest: str, travel_date: str) -> int:
    context = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) "
                   "Gecko/20100101 Firefox/130.0"
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )

    page = context.new_page()
    scrape_ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    page.on("response", make_response_handler(origin, dest, travel_date, scrape_ts))

    print(f"Scraping {origin}->{dest} for {travel_date} ...")
    try:
        # A bounded navigation keeps a blocked search page from freezing the run.
        page.goto(build_url(origin, dest, travel_date),
                  wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(7000)
    except Exception as exc:
        print(f"  [error] navigation failed: {exc}")
    finally:
        context.close()

    safe_date = travel_date.replace("/", "-")
    matches = list(RAW_DIR.glob(f"{origin}_{dest}_{safe_date}_AirBus_New_{scrape_ts}.json"))
    if not matches:
        print(f"  [warn] no AirBus_New payload for {origin}->{dest} {travel_date}")
        return 0

    with open(matches[0], encoding="utf-8") as f:
        raw = json.load(f)

    advance_days = (datetime.strptime(travel_date, "%d/%m/%Y") - datetime.now()).days
    records = parse_easemytrip(raw, origin, dest, travel_date, advance_days,
                               datetime.now().strftime("%Y-%m-%d"))
    insert_fares(records)
    print(f"  [db] inserted {len(records)} fare records")
    return len(records)


def run_scrape(routes=None, windows=None, fresh_raw: bool = True,
               progress: Callable[[int, int, str], None] | None = None) -> int:
    """Scrape the basket with bounded waits and optional progress reporting."""
    global RAW_DIR
    init_db()
    RAW_DIR = _raw_dir()
    if fresh_raw:
        shutil.rmtree(RAW_DIR, ignore_errors=True)
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    selected_routes = list(routes or ROUTES)
    selected_windows = list(windows or ADVANCE_WINDOWS)
    jobs = [(origin, dest, days) for origin, dest in selected_routes
            for days in selected_windows]
    total_records = 0
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            for completed, (origin, dest, days_ahead) in enumerate(jobs, start=1):
                if progress:
                    progress(completed - 1, len(jobs),
                             f"Fetching {origin} → {dest} ({days_ahead} days ahead)")
                travel_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%d/%m/%Y")
                total_records += scrape_route(browser, origin, dest, travel_date)
                if completed < len(jobs):
                    time.sleep(random.uniform(0.8, 1.5))
        finally:
            browser.close()
    if progress:
        progress(len(jobs), len(jobs), "Live refresh complete")
    return total_records


if __name__ == "__main__":
    print(f"stored {run_scrape()} records")
