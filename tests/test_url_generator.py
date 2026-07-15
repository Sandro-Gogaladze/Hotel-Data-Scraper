from datetime import date
from urllib.parse import parse_qs, urlparse

from scheduled.url_generator import generate_search_urls, load_recipe

RECIPE = {
    "base_url": "https://www.booking.com/searchresults.en-gb.html",
    "params": {"dest_id": "79", "dest_type": "country", "nflt": "ht_id=204"},
    "checkin_day": 15,
    "checkout_day": 16,
    "months_ahead": [0, 1, 2],
}


def _checkin_checkout(url: str):
    q = parse_qs(urlparse(url).query)
    return q["checkin"][0], q["checkout"][0]


def test_generates_one_url_per_month_offset():
    urls = generate_search_urls(RECIPE, reference_date=date(2026, 8, 5))
    assert len(urls) == 3


def test_dates_for_mid_year_reference():
    urls = generate_search_urls(RECIPE, reference_date=date(2026, 8, 5))
    dates = [_checkin_checkout(u) for u in urls]

    assert dates == [
        ("2026-08-15", "2026-08-16"),
        ("2026-09-15", "2026-09-16"),
        ("2026-10-15", "2026-10-16"),
    ]


def test_year_rollover_when_reference_is_november():
    urls = generate_search_urls(RECIPE, reference_date=date(2026, 11, 20))
    dates = [_checkin_checkout(u) for u in urls]

    assert dates == [
        ("2026-11-15", "2026-11-16"),
        ("2026-12-15", "2026-12-16"),
        ("2027-01-15", "2027-01-16"),  # rolls into next year
    ]


def test_reference_late_in_month_does_not_skip_current_month():
    # Running on the 28th should still target the 15th-16th of the SAME month
    # for offset 0, not skip to next month just because "the 15th already passed".
    urls = generate_search_urls(RECIPE, reference_date=date(2026, 3, 28))
    dates = [_checkin_checkout(u) for u in urls]

    assert dates[0] == ("2026-03-15", "2026-03-16")


def test_recipe_params_are_preserved_in_url():
    urls = generate_search_urls(RECIPE, reference_date=date(2026, 8, 5))
    q = parse_qs(urlparse(urls[0]).query)

    assert q["dest_id"] == ["79"]
    assert q["dest_type"] == ["country"]
    assert q["nflt"] == ["ht_id=204"]
    assert urls[0].startswith(RECIPE["base_url"])


def test_shipped_recipe_file_loads_and_produces_valid_urls():
    recipe = load_recipe()
    urls = generate_search_urls(recipe, reference_date=date(2026, 8, 5))

    assert len(urls) == 3
    for url in urls:
        assert url.startswith("https://www.booking.com/searchresults")
        q = parse_qs(urlparse(url).query)
        assert "checkin" in q and "checkout" in q
        assert q["dest_id"] == ["79"]
