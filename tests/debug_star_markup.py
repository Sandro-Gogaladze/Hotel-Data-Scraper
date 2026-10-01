#!/usr/bin/env python3
"""Temporary: can any URL parameter make booking.com show star ratings to a US-based
(GitHub runner) visitor? Locally stars are present; on runners they are absent entirely.

Delete together with .github/workflows/debug-star-markup.yml.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

from utils.anti_detection import get_browser_launch_options  # noqa: E402

HOTEL = ("https://www.booking.com/hotel/ge/golden-tulip-borjomi{path_lang}.html?aid=2311236&ucfs=1&arphpl=1"
         "&checkin=2026-10-15&checkout=2026-10-16&dest_id=-2327786&dest_type=city"
         "&group_adults=2&req_adults=2&no_rooms=1&group_children=0&req_children=0"
         "&hpos=1&hapos=1&sr_order=popularity&selected_currency=GEL&from=searchresults{extra}")

VARIANTS = {
    "baseline": dict(path_lang="", extra=""),
    "lang=en-gb param": dict(path_lang="", extra="&lang=en-gb"),
    "en-gb in path": dict(path_lang=".en-gb", extra=""),
    "cc1=ge": dict(path_lang="", extra="&cc1=ge"),
    "en-gb path + cc1 + lang": dict(path_lang=".en-gb", extra="&cc1=ge&lang=en-gb"),
}

CHECK = r"""() => ({
    stars: !!document.querySelector('[data-testid="rating-stars"], [data-testid="rating-squares"]'),
    aria: [...new Set([...document.querySelectorAll('[aria-label]')]
        .map(e => e.getAttribute('aria-label')).filter(l => /out of 5/i.test(l)))].slice(0, 2),
    title: document.title.split(',')[0].slice(0, 28),
    currency: (document.body.innerText.match(/GEL|US\$|€/) || ['?'])[0],
})"""

with sync_playwright() as p:
    browser = p.chromium.launch(**get_browser_launch_options(headless=True))
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    for name, parts in VARIANTS.items():
        try:
            page.goto(HOTEL.format(**parts), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            r = page.evaluate(CHECK)
            print(f"VARIANT {name:26s} stars={r['stars']!s:5s} aria={r['aria']} page={r['title']!r} cur={r['currency']}")
        except Exception as e:
            print(f"VARIANT {name:26s} ERROR {str(e)[:70]}")
    browser.close()
