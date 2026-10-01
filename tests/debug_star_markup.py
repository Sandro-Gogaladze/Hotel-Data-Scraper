#!/usr/bin/env python3
"""Temporary: print how booking.com renders star ratings in this environment.

Stars come back empty on GitHub runners but fine locally, so dump what the page
actually contains. Delete together with .github/workflows/debug-star-markup.yml.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import date, timedelta  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

from scraper.search_page.extractor import batch_extract_basic_info  # noqa: E402
from scraper.search_page.locators import HOTEL_CARD  # noqa: E402
from utils.anti_detection import get_browser_launch_options  # noqa: E402

checkin = date.today() + timedelta(days=30)
URL = ("https://www.booking.com/searchresults.html"
       f"?ss=Paris&checkin={checkin.isoformat()}&checkout={(checkin + timedelta(days=2)).isoformat()}"
       "&group_adults=2&no_rooms=1&group_children=0&nflt=ht_id%3D204")

JS = r"""() => {
    const cards = [...document.querySelectorAll('div[data-testid="property-card"]')];
    return {
        url: location.href,
        lang: document.documentElement.lang,
        cards: cards.length,
        testids_anywhere: [...new Set([...document.querySelectorAll('[data-testid]')]
            .map(e => e.getAttribute('data-testid')).filter(t => /rating|star|quality|class/i.test(t)))],
        aria_out_of: [...new Set([...document.querySelectorAll('[aria-label*="out of"]')]
            .map(e => e.tagName + ' | ' + e.getAttribute('aria-label')))].slice(0, 5),
        aria_star: [...new Set([...document.querySelectorAll('[aria-label*="tar"]')]
            .map(e => e.tagName + ' | ' + e.getAttribute('aria-label')))].slice(0, 5),
        first_cards: cards.slice(0, 3).map(c => ({
            name: c.querySelector('[data-testid="title"]')?.innerText,
            text_head: c.innerText.split('\n').slice(0, 6).join(' | '),
            rating_html: (c.querySelector('[data-testid^="rating"]')?.outerHTML || '(no rating element)')
                .replace(/<svg[\s\S]*?<\/svg>/g, '<svg/>').slice(0, 400),
            html_head: c.innerHTML.replace(/<svg[\s\S]*?<\/svg>/g, '<svg/>').slice(0, 700),
        })),
    };
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(**get_browser_launch_options(headless=True))
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(HOTEL_CARD, timeout=30000)
    page.wait_for_timeout(2000)

    info = page.evaluate(JS)
    print("URL:", info["url"][:120])
    print("lang:", info["lang"], "| cards:", info["cards"])
    print("rating-ish data-testids on page:", info["testids_anywhere"])
    print("aria-labels containing 'out of':", info["aria_out_of"])
    print("aria-labels containing 'tar' (star):", info["aria_star"])
    for card in info["first_cards"]:
        print("\n--- card:", card["name"])
        print("  text:", card["text_head"])
        print("  rating element:", card["rating_html"])
        print("  html head:", card["html_head"])

    print("\nScraped Stars values:", [h["Stars"] for h in batch_extract_basic_info(page)][:8])
    browser.close()

# --- also check the hotel page, as a possible source of the star rating ---
with sync_playwright() as p:
    browser = p.chromium.launch(**get_browser_launch_options(headless=True))
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(HOTEL_CARD, timeout=30000)
    # fixed, known 4-star property so local and CI compare the same page
    link = ("https://www.booking.com/hotel/ge/golden-tulip-borjomi.html?aid=2311236&ucfs=1&arphpl=1"
            "&checkin=2026-10-15&checkout=2026-10-16&dest_id=-2327786&dest_type=city"
            "&group_adults=2&req_adults=2&no_rooms=1&group_children=0&req_children=0"
            "&hpos=1&hapos=1&sr_order=popularity&selected_currency=GEL&from=searchresults")
    page.goto(link, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    hotel = page.evaluate(r"""() => ({
        title: document.title.split(',')[0],
        testids: [...new Set([...document.querySelectorAll('[data-testid]')]
            .map(e => e.getAttribute('data-testid')).filter(t => /rating|star|class|quality/i.test(t)))],
        aria: [...new Set([...document.querySelectorAll('[aria-label]')]
            .map(e => e.getAttribute('aria-label')).filter(l => /out of|star/i.test(l)))].slice(0, 6),
        rating_html: (document.querySelector('[data-testid="rating-stars"], [data-testid="rating-squares"], .hp__hotel_ratings')?.outerHTML
            || '(none)').replace(/<svg[\s\S]*?<\/svg>/g, '<svg/>').slice(0, 300),
    })""")
    print("\n=== HOTEL PAGE:", hotel["title"])
    print("  rating-ish data-testids:", hotel["testids"])
    print("  aria-labels:", hotel["aria"])
    print("  rating element:", hotel["rating_html"])
    browser.close()
