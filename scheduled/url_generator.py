"""
Generates this run's Booking.com search URLs from a fixed "recipe" (destination
+ filters, stored in search_recipe.json) plus a rolling date window computed
from whatever date the caller actually runs on — no manual monthly editing of
URLs required.

Default recipe: current month + next 2 months, each searched for the recipe's
checkin_day -> checkout_day (e.g. the 15th -> 16th).
"""

import calendar
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

RECIPE_PATH = os.path.join(os.path.dirname(__file__), "search_recipe.json")


def load_recipe(path: str = RECIPE_PATH) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _add_months(d: date, months: int) -> date:
    """Return the 1st of the month `months` after d's month (handles year rollover)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _day_in_month(month_start: date, day: int) -> date:
    """Clamp/roll `day` into month_start's month, rolling into the next month if
    the day doesn't exist there (e.g. day 31 in a 30-day month)."""
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    if day <= last_day:
        return month_start.replace(day=day)
    return _add_months(month_start, 1).replace(day=day - last_day)


def generate_search_urls(
    recipe: Optional[Dict[str, Any]] = None,
    reference_date: Optional[date] = None,
) -> List[str]:
    """Build one search URL per entry in recipe['months_ahead'], each with
    checkin/checkout set to the recipe's day-of-month in that target month,
    relative to reference_date (defaults to today)."""
    recipe = recipe if recipe is not None else load_recipe()
    reference_date = reference_date or date.today()

    urls = []
    for offset in recipe["months_ahead"]:
        target_month_start = _add_months(reference_date.replace(day=1), offset)
        checkin = _day_in_month(target_month_start, recipe["checkin_day"])
        checkout = _day_in_month(target_month_start, recipe["checkout_day"])

        params = dict(recipe["params"])
        params["checkin"] = checkin.isoformat()
        params["checkout"] = checkout.isoformat()

        urls.append(f"{recipe['base_url']}?{urlencode(params)}")

    return urls


if __name__ == "__main__":
    for url in generate_search_urls():
        print(url)
