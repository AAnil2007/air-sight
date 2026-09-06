"""EaseMyTrip live scraper using Playwright (Firefox)."""
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List

from database import DB_PATH, insert_fare, load_fares
from parser import parse_emt_payload, remove_outliers
from routes_config import ADVANCE_WINDOWS, ROUTES


def _data_dir() -> Path:
    d = Path(__file__).parent / "data" / "raw"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        fallback = Path.home() / ".airsight" / "data" / "raw"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _build_url(origin: str, dest: str, d: date) -> str:
    return (
        f"https://flight.easemytrip.com/FlightList/Index?"
        f"srch={origin}-{dest}-|{d.strftime('%Y-%m-%d')}|false|1,0|1,0"
    )


def _parse_network_response_text(text: str, origin: str, dest: str, scrape_date: str, departure_date: str) -> List[dict]:
    try:
        payload = json.loads(text)
    except Exception:
        return []
    rows = parse_emt_payload(payload, origin, dest, scrape_date, departure_date)
    return remove_outliers(rows)


async def _scrape_one_route_async(page, origin: str, dest: str, departure_date: date, timeout_ms: int = 35000) -> List[dict]:
    """Open an EaseMyTrip result page and capture the AirBus_New JSON response."""
    url = _build_url(origin, dest, departure_date)
    scrape_date = date.today().isoformat()
    rows: List[dict] = []

    # intercept network responses matching the AirBus_New endpoint
    def handle_response(resp):
        nonlocal rows
        try:
            if "AirBus_New" in resp.url and resp.status == 200:
                text = resp.text()
                found = _parse_network_response_text(text, origin, dest, scrape_date, departure_date.isoformat())
                if found:
                    rows.extend(found)
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        await page.wait_for_timeout(2500)
    except Exception:
        pass

    # Fallback: look for JSON in page content if network intercept missed
    if not rows:
        try:
            content = await page.content()
            matches = re.findall(r'AirBus_New\?[^"\']+', content)
            for m in matches:
                full = m if m.startswith("http") else "https://flight.easemytrip.com" + m
                try:
                    import requests
                    r = requests.get(full, timeout=15)
                    found = _parse_network_response_text(r.text, origin, dest, scrape_date, departure_date.isoformat())
                    if found:
                        rows.extend(found)
                except Exception:
                    pass
        except Exception:
            pass

    page.remove_listener("response", handle_response)
    return remove_outliers(rows)


async def run_scrape_async(max_routes: int = 6, progress_callback=None) -> dict:
    """Scrape the basket for the next N advance windows."""
    from playwright.async_api import async_playwright

    today = date.today()
    data_dir = _data_dir()
    summary = {"scraped": 0, "stored": 0, "routes": []}

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        count = 0
        for origin, dest, weight in ROUTES:
            if count >= max_routes:
                break
            count += 1
            route_label = f"{origin}-{dest}"
            if progress_callback:
                progress_callback(f"Scraping {route_label} ({count}/{max_routes})...")

            for adv in ADVANCE_WINDOWS[:3]:  # default to 1, 7, 15 days to stay fast
                dep = today + timedelta(days=adv)
                rows = await _scrape_one_route_async(page, origin, dest, dep)
                summary["scraped"] += len(rows)
                for r in rows:
                    insert_fare(r)
                    summary["stored"] += 1

        await browser.close()

    summary["routes"] = scrape_dates_summary()
    return summary


def scrape_dates_summary() -> List[str]:
    from database import scrape_dates
    return scrape_dates()


def run_scrape_sync(max_routes: int = 6) -> dict:
    import asyncio
    return asyncio.run(run_scrape_async(max_routes=max_routes))
