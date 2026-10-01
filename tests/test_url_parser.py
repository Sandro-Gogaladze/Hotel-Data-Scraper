from urllib.parse import parse_qs, urlparse

from utils.url_parser import extract_booking_params, propagate_search_params

HOTEL_URL = "https://www.booking.com/hotel/ge/frida.en-gb.html?aid=2311236&checkin=2026-10-15&group_adults=2"


def test_propagate_copies_currency_and_lang_to_hotel_link():
    search = "https://www.booking.com/searchresults.en-gb.html?ss=Georgia&selected_currency=GEL&lang=en-gb"

    out = propagate_search_params(search, HOTEL_URL)

    q = parse_qs(urlparse(out).query)
    assert q["selected_currency"] == ["GEL"]
    # without lang, booking.com shows no star rating to a US-based visitor
    assert q["lang"] == ["en-gb"]
    assert q["checkin"] == ["2026-10-15"]  # existing params kept
    assert urlparse(out).path == "/hotel/ge/frida.en-gb.html"


def test_propagate_overrides_existing_values_on_hotel_link():
    search = "https://www.booking.com/searchresults.html?selected_currency=USD"

    out = propagate_search_params(search, HOTEL_URL + "&selected_currency=EUR")

    assert parse_qs(urlparse(out).query)["selected_currency"] == ["USD"]


def test_propagate_leaves_link_alone_when_search_sets_neither():
    assert propagate_search_params("https://www.booking.com/searchresults.html?ss=Tbilisi", HOTEL_URL) == HOTEL_URL
    assert propagate_search_params("https://www.booking.com/searchresults.html?selected_currency=GEL", "N/A") == "N/A"


def test_extract_full_params():
    url = (
        "https://www.booking.com/searchresults.html?"
        "ss=Tbilisi&checkin=2026-08-01&checkout=2026-08-05"
        "&group_adults=2&group_children=1&no_rooms=1"
        "&nflt=mealplan%3D1%3Bht_id%3D204"
    )
    params = extract_booking_params(url)

    assert params["destination"] == "Tbilisi"
    assert params["check_in"] == "2026-08-01"
    assert params["check_out"] == "2026-08-05"
    assert params["adults"] == "2"
    assert params["children"] == "1"
    assert params["rooms"] == "1"
    assert params["duration"] == "4 nights"
    assert "Breakfast included" in params["filters"]
    assert "Property type: Hotel" in params["filters"]


def test_extract_params_missing_fields_default_to_unknown():
    url = "https://www.booking.com/searchresults.html?ss=Batumi"

    params = extract_booking_params(url)

    assert params["destination"] == "Batumi"
    assert params["check_in"] == "Unknown"
    assert params["check_out"] == "Unknown"
    assert params["adults"] == "Unknown"
    assert params["filters"] == []
    assert "duration" not in params


def test_extract_params_alternate_date_format():
    url = (
        "https://www.booking.com/searchresults.html?"
        "ss=Kutaisi"
        "&checkin_year=2026&checkin_month=9&checkin_monthday=3"
        "&checkout_year=2026&checkout_month=9&checkout_monthday=6"
    )

    params = extract_booking_params(url)

    assert params["check_in"] == "2026-09-03"
    assert params["check_out"] == "2026-09-06"


def test_extract_params_unknown_filter_code_passthrough():
    url = "https://www.booking.com/searchresults.html?ss=Batumi&nflt=mealplan%3D9"

    params = extract_booking_params(url)

    assert params["filters"] == ["Meal plan: 9"]


def test_extract_params_malformed_url_does_not_raise():
    params = extract_booking_params("not a url at all")

    assert params["destination"] == "Unknown"
