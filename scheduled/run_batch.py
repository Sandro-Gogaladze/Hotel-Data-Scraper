#!/usr/bin/env python3
"""
Non-interactive scraper runner for scheduled/automated use (e.g. GitHub Actions).

Generates this run's search URLs from scheduled/search_recipe.json (current
month + next 2, see url_generator.py), then runs the same scraping pipeline
main.py uses for each one in turn. A single URL failing doesn't abort the
others - the whole point of a monthly unattended run is that one bad search
shouldn't cost you the other two.

Writes a JSON summary (default: scheduled_results.json) that
scheduled/send_report.py reads to build the email.
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

from config import HEADLESS, OUTPUT_DIR  # noqa: E402
from export.excel import save_to_excel  # noqa: E402
from scheduled.url_generator import generate_search_urls  # noqa: E402
from scraper.coordinator import process_booking_search  # noqa: E402
from utils.anti_detection import add_random_delay, get_browser_launch_options  # noqa: E402
from utils.logger import log_message  # noqa: E402

DEFAULT_RESULTS_PATH = os.path.join(PROJECT_ROOT, "scheduled_results.json")


def run_one(browser: Any, url: str) -> Dict[str, Any]:
    start = time.time()
    today = datetime.today().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H-%M-%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"{today}_{timestamp}_scheduled.xlsx")

    try:
        add_random_delay(1.0, 3.0)
        hotels_data = process_booking_search(browser, url)
        duration = time.time() - start

        if not hotels_data:
            log_message(f"Scheduled run: no hotel data for {url}", "error")
            return {"url": url, "success": False, "error": "No hotel data collected", "duration": duration}

        save_to_excel(hotels_data, output_file, search_url=url, duration_seconds=duration)
        return {
            "url": url,
            "success": True,
            "output_file": output_file,
            "hotel_count": len(hotels_data),
            "duration": duration,
        }
    except Exception as e:
        duration = time.time() - start
        log_message(f"Scheduled run failed for {url}: {e}", "error")
        return {"url": url, "success": False, "error": str(e), "duration": duration}


def run_batch() -> List[Dict[str, Any]]:
    urls = generate_search_urls()
    log_message(f"Scheduled batch run: {len(urls)} searches — headless={HEADLESS}", "info")

    results = []
    with sync_playwright() as p:
        launch_options = get_browser_launch_options(headless=HEADLESS, worker_id=0)
        browser = p.chromium.launch(**launch_options)
        try:
            for i, url in enumerate(urls, 1):
                log_message(f"[{i}/{len(urls)}] Running scheduled search: {url}", "info")
                results.append(run_one(browser, url))
        finally:
            browser.close()

    return results


def main() -> None:
    results_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESULTS_PATH

    results = run_batch()

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    for r in results:
        status = "OK" if r["success"] else "FAILED"
        print(f"[{status}] {r['url']}")

    log_message(f"Scheduled batch results written to {results_path}", "info")

    # Non-zero exit only if every single search failed - a partial success (1 or
    # 2 out of 3) should still report success so the email step reports it
    # properly rather than the workflow treating it as a hard failure.
    if not any(r["success"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
