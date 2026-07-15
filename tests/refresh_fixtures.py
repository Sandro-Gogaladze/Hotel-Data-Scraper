#!/usr/bin/env python3
"""
Capture live HTML from booking.com for manual comparison against the curated
test fixtures in tests/fixtures/. Useful when the live smoke test
(tests/test_live_smoke.py, run via `uv run pytest -m live`) starts failing and
you need to see exactly what changed.

Usage:
    uv run python tests/refresh_fixtures.py "<search results url>" "<hotel detail url>"

Saves timestamped snapshots to tests/fixtures/live_captures/ (gitignored). These
are NOT consumed by the test suite — they're for you to diff by eye against
tests/fixtures/search_results.html and tests/fixtures/hotel_detail_rooms.html to
spot what markup/selectors changed, then update scraper/*/locators.py and the
extraction JS to match.
"""

import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

from scraper.hotel_page.locators import NO_AVAILABILITY, ROOM_ROW  # noqa: E402
from scraper.search_page.locators import HOTEL_CARD  # noqa: E402
from utils.anti_detection import get_browser_launch_options  # noqa: E402


def capture(url: str, wait_selector: str, out_name: str, out_dir: str) -> None:
    with sync_playwright() as p:
        launch_options = get_browser_launch_options(headless=True, worker_id=0)
        browser = p.chromium.launch(**launch_options)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(wait_selector, timeout=20000)
            html = page.content()
        finally:
            browser.close()

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, out_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved {path} ({len(html)} bytes)")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: uv run python tests/refresh_fixtures.py <search_url> <hotel_url>")
        sys.exit(1)

    search_url, hotel_url = sys.argv[1], sys.argv[2]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = os.path.join(os.path.dirname(__file__), "fixtures", "live_captures")

    capture(search_url, HOTEL_CARD, f"search_results_{timestamp}.html", out_dir)
    capture(hotel_url, f"{ROOM_ROW}, {NO_AVAILABILITY}", f"hotel_detail_{timestamp}.html", out_dir)

    print("\nDiff these against tests/fixtures/search_results.html and")
    print("tests/fixtures/hotel_detail_rooms.html to see what markup changed.")


if __name__ == "__main__":
    main()
