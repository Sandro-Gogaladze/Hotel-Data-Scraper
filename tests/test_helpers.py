from utils.helpers import clean_price


def test_clean_price_with_currency_symbol_and_commas():
    assert clean_price("$1,234") == 1234


def test_clean_price_with_decimal():
    assert clean_price("€99.50") == 99


def test_clean_price_plain_number():
    assert clean_price("450") == 450


def test_clean_price_with_currency_code():
    assert clean_price("GEL 35") == 35


def test_clean_price_empty_string_returns_none():
    assert clean_price("") is None


def test_clean_price_no_digits_returns_none():
    assert clean_price("N/A") is None
