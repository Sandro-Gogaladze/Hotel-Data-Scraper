"""
Opt-in live smoke test — hits the real booking.com site to confirm our
selectors still resolve. This is the only test in the suite that can actually
detect "booking.com changed their markup"; the fixture-based tests
(test_search_page_extraction.py, test_hotel_page_extraction.py) only catch
regressions in our own code against a frozen snapshot.

Skipped by default (pyproject.toml sets `addopts = "-m 'not live'"`). Run with:

    uv run pytest -m live

If this fails, capture a fresh snapshot with tests/refresh_fixtures.py and diff
it against tests/fixtures/*.html to see what markup changed, then update
scraper/*/locators.py and the extraction JS accordingly.
"""

from datetime import date, timedelta

import pytest
from playwright.sync_api import sync_playwright

from scraper.hotel_page.detailed_extractor import extract_rooms_with_js
from scraper.hotel_page.locators import NO_AVAILABILITY, ROOM_ROW
from scraper.search_page.extractor import batch_extract_basic_info
from scraper.search_page.locators import HOTEL_CARD
from utils.anti_detection import get_browser_launch_options

pytestmark = pytest.mark.live


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _search_url() -> str:
    """Hotels only (nflt=ht_id=204), like the scheduled runs. Without that filter the
    results are mostly apartments and guesthouses, which have no star rating, so the
    star check below would fail for a reason that has nothing to do with our selectors."""
    checkin = date.today() + timedelta(days=30)
    checkout = checkin + timedelta(days=2)
    return (
        "https://www.booking.com/searchresults.html"
        f"?ss=Paris&checkin={checkin.isoformat()}&checkout={checkout.isoformat()}"
        "&group_adults=2&no_rooms=1&group_children=0&nflt=ht_id%3D204"
    )


@pytest.fixture(scope="module")
def live_browser():
    with sync_playwright() as p:
        launch_options = get_browser_launch_options(headless=True, worker_id=0)
        browser = p.chromium.launch(**launch_options)
        yield browser
        browser.close()


def test_search_page_selectors_still_resolve(live_browser):
    page = live_browser.new_page()
    try:
        page.goto(_search_url(), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(HOTEL_CARD, timeout=15000)

        hotels = batch_extract_basic_info(page)

        assert len(hotels) > 0, "No property cards extracted — search page selectors may be stale"

        first = hotels[0]
        assert first["Hotel Name"] not in ("", "N/A"), "Hotel name selector may be stale"
        assert first["Hotel Link"].startswith("http"), "Hotel link selector may be stale"

        # Not every property has stars or reviews, but a whole page with none means the
        # selector broke. This is how Stars went 100% N/A in Sept 2026 while this test
        # still passed.
        assert any(h["Stars"] != "N/A" for h in hotels), "Star rating selector may be stale"
        assert any(_is_number(h["Review Score"]) for h in hotels), "Review score selector may be stale"
    finally:
        page.close()


def test_hotel_detail_page_selectors_still_resolve(live_browser):
    # Pull a real hotel link from a live search first — we need somewhere real to navigate to.
    search_page = live_browser.new_page()
    try:
        search_page.goto(_search_url(), wait_until="domcontentloaded", timeout=30000)
        search_page.wait_for_selector(HOTEL_CARD, timeout=15000)
        hotels = batch_extract_basic_info(search_page)
    finally:
        search_page.close()

    assert hotels, "Need at least one hotel from search results to test the detail page"
    hotel_link = hotels[0]["Hotel Link"]

    detail_page = live_browser.new_page()
    try:
        detail_page.goto(hotel_link, wait_until="domcontentloaded", timeout=30000)
        selector = f"{ROOM_ROW}, {NO_AVAILABILITY}"
        detail_page.wait_for_selector(selector, timeout=20000)

        if detail_page.query_selector(NO_AVAILABILITY):
            pytest.skip(
                "Hotel had no availability for the test dates — selectors resolved, "
                "nothing more to verify"
            )

        rooms = extract_rooms_with_js(detail_page)
        assert len(rooms) > 0, "No rooms extracted — hotel detail page selectors may be stale"
        assert rooms[0]["price"] > 0, "Displayed room price selectors may be stale"
        assert any(r["max_persons"] is not None for r in rooms), "Room occupancy selectors may be stale"
    finally:
        detail_page.close()
