"""
Regression tests for hotel-detail-page extraction.

Same approach as test_search_page_extraction.py: real headless Chromium against a
static local HTML fixture. Catches regressions in our own extraction code, not
live-site drift (see tests/test_live_smoke.py for that).
"""

from conftest import load_fixture

from scraper.hotel_page.detailed_extractor import analyze_rooms, extract_rooms_with_js
from scraper.hotel_page.locators import NO_AVAILABILITY


def test_extract_rooms_with_js(page):
    page.set_content(load_fixture("hotel_detail_rooms.html"))

    rooms = extract_rooms_with_js(page)

    assert len(rooms) == 3

    room_a, room_b, room_c = rooms

    assert room_a["price"] == 180
    assert room_a["max_persons"] == 2
    assert room_a["free_cancellation"] is True
    assert room_a["non_refundable"] is False
    assert room_a["has_breakfast_mention"] is True
    assert room_a["breakfast_included"] is True

    assert room_b["price"] == 132
    assert room_b["max_persons"] == 2  # derived from occupancy icons, not sr-only text
    assert room_b["free_cancellation"] is False
    assert room_b["non_refundable"] is True
    assert room_b["has_breakfast_mention"] is True
    assert room_b["breakfast_included"] is False  # "extra" disqualifies it

    assert room_c["price"] == 250
    assert room_c["max_persons"] == 3
    assert room_c["free_cancellation"] is False
    assert room_c["non_refundable"] is False
    assert room_c["has_breakfast_mention"] is False


def test_no_availability_selector_matches_fixture(page):
    page.set_content(load_fixture("hotel_detail_no_availability.html"))

    assert page.query_selector(NO_AVAILABILITY) is not None


def test_analyze_rooms_picks_min_price_and_min_2_person_price(monkeypatch):
    # analyze_rooms calls out to GPT only when a room's breakfast text is ambiguous;
    # stub it so this test doesn't depend on network access or an API key.
    monkeypatch.setattr(
        "scraper.hotel_page.detailed_extractor.analyze_breakfast_with_gpt4",
        lambda text: "included" in text.lower(),
    )

    rooms = [
        {
            "price": 250,
            "max_persons": 3,
            "free_cancellation": False,
            "non_refundable": False,
            "has_breakfast_mention": False,
            "breakfast_included": False,
            "breakfast_text": "",
        },
        {
            "price": 132,
            "max_persons": 2,
            "free_cancellation": False,
            "non_refundable": True,
            "has_breakfast_mention": True,
            "breakfast_included": False,
            "breakfast_text": "Breakfast €15 extra per person",
        },
        {
            "price": 180,
            "max_persons": 2,
            "free_cancellation": True,
            "non_refundable": False,
            "has_breakfast_mention": True,
            "breakfast_included": False,
            "breakfast_text": "Breakfast included in the price",
        },
    ]

    result = analyze_rooms(rooms, "Test Hotel")

    # cheapest room overall is the 132 one
    assert result["Min Room Price"] == 132
    assert result["Min Room Price Non-refundable"] is True
    assert result["Min Room Price Breakfast Included"] is False

    # cheapest room among 2-person rooms is also the 132 one (same room here)
    assert result["Min 2 Person Price"] == 132


def test_analyze_rooms_empty_list_returns_na_defaults():
    result = analyze_rooms([], "Empty Hotel")

    assert result["Min Room Price"] == "N/A"
    assert result["Min 2 Person Price"] == "N/A"
