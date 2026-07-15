"""
Regression tests for search-results-page extraction.

These load a local HTML fixture (built to mirror booking.com's real markup as of
when it was captured) into a real headless Chromium page and run the actual
extraction functions against it. They catch regressions introduced by changes to
our own extraction code or selectors; they do NOT detect drift on the live site,
since the fixture is static. See tests/test_live_smoke.py for that.
"""

from conftest import load_fixture

from scraper.search_page.extractor import (
    batch_extract_basic_info,
    extract_hotel_basic_info,
    get_all_hotel_elements,
)


def test_batch_extract_basic_info(page):
    page.set_content(load_fixture("search_results.html"))

    hotels = batch_extract_basic_info(page)

    assert len(hotels) == 2

    frida, kazbegi = hotels

    assert frida["Hotel Name"] == "Hotel Frida"
    assert frida["Hotel Link"] == "https://www.booking.com/hotel/ge/frida.html"
    assert frida["Address"] == "123 Rustaveli Ave, Tbilisi"
    assert frida["Price"] == "$180"
    assert frida["Review Score"] == "8.7"
    assert frida["Review Text"] == "Excellent"
    assert frida["Number of Reviews"] == "1,204 reviews"
    assert frida["Stars"] == "4 out of 5 stars"

    assert kazbegi["Hotel Name"] == "Kazbegi Estate"
    assert kazbegi["Address"] == "Stepantsminda, Georgia"
    assert kazbegi["Review Score"] == "7.2"
    assert kazbegi["Review Text"] == "Good"
    assert kazbegi["Number of Reviews"] == "340 reviews"


def test_dom_fallback_extraction_matches_batch_path(page):
    """The per-element Playwright-locator fallback should agree with the JS batch path."""
    page.set_content(load_fixture("search_results.html"))

    elements = get_all_hotel_elements(page)
    assert len(elements) == 2

    frida = extract_hotel_basic_info(elements[0], 0)

    assert frida["Hotel Name"] == "Hotel Frida"
    assert frida["Hotel Link"] == "https://www.booking.com/hotel/ge/frida.html"
    assert frida["Address"] == "123 Rustaveli Ave, Tbilisi"
    assert frida["Review Score"] == "8.7"
    assert frida["Review Text"] == "Excellent"
    assert frida["Stars"] == "4 out of 5 stars"
