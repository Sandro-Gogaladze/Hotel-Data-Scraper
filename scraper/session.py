"""
Pin one Booking.com visitor session for a whole scraping run.

Booking.com A/B-tests page versions per visitor, keyed on cookies, and every fresh
browser session is assigned one at random. In Sept 2026 roughly a third of new sessions
got a room table listing only rates for the searched party - hiding cheaper "1 guest"
rates - so otherwise identical runs disagreed with each other and with what a regular
browser shows. A session keeps its version for as long as its cookies are reused.

establish_session() opens fresh sessions until one gets the full room table (a per-row
"Number of guests" column, the long-standing version), and returns its cookies. The
search page and every worker then load that same session, so a run sees one consistent
version of the site.
"""

import os
import sys
from typing import Any, Dict, Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import PAGE_LOAD_TIMEOUT, SESSION_ATTEMPTS
from scraper.hotel_page.locators import NO_AVAILABILITY, ROOM_ROW
from scraper.search_page.locators import HOTEL_CARD, HOTEL_LINK
from utils.anti_detection import configure_page_for_stealth
from utils.logger import log_message
from utils.url_parser import propagate_search_params

FULL_ROOM_TABLE = "td.hprt-table-cell-occupancy"             # per-row occupancy column
REDUCED_ROOM_TABLE = ".hprt-roomtype-occupancy-info"         # "Sleeps: 2 adults" per room type
# Some properties always use the "Sleeps" table, even in full sessions, while a cut-down
# session never shows the full table - so a session is full if ANY probed hotel shows it.
PROBE_HOTELS = 5


def room_table_version(page: Any) -> Optional[str]:
    """"full", "reduced", or None if the page has no room table to tell by."""
    if page.query_selector(FULL_ROOM_TABLE):
        return "full"
    if page.query_selector(REDUCED_ROOM_TABLE):
        return "reduced"
    return None


def _probe(context: Any, search_url: str) -> Optional[str]:
    page = context.new_page()
    configure_page_for_stealth(page)
    page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    page.wait_for_selector(HOTEL_CARD, timeout=20000)
    links = page.eval_on_selector_all(HOTEL_LINK, f"els => els.slice(0, {PROBE_HOTELS}).map(e => e.href)")
    seen = None
    for link in links:
        try:
            page.goto(propagate_search_params(search_url, link), wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            page.wait_for_selector(f"{ROOM_ROW}, {NO_AVAILABILITY}", timeout=25000)
        except Exception as e:
            log_message(f"Session probe: skipping a hotel that didn't load: {e}", "debug")
            continue
        version = room_table_version(page)
        if version == "full":
            return "full"
        seen = seen or version
    return seen


def establish_session(browser: Any, search_url: str, attempts: int = SESSION_ATTEMPTS) -> Optional[Dict[str, Any]]:
    """
    Find a session that gets the full room table and return its storage state (cookies).

    Args:
        browser: A Playwright Browser.
        search_url: The run's search URL; its first hotels are used as probes.
        attempts: How many fresh sessions to try.

    Returns:
        A storage_state dict to pass to browser.new_context(storage_state=...), or None if
        no session got the full table (the run then continues with fresh sessions).
    """
    for attempt in range(1, attempts + 1):
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        try:
            version = _probe(context, search_url)
            if version == "full":
                log_message(f"Session: got the full room table on attempt {attempt}", "info")
                return context.storage_state()
            log_message(f"Session attempt {attempt}/{attempts}: room table version {version!r}, retrying", "info")
        except Exception as e:
            log_message(f"Session attempt {attempt}/{attempts} failed: {e}", "warning")
        finally:
            context.close()

    log_message("Could not get a session with the full room table - results may miss cheaper "
                "'1 guest' rates and differ from what a regular browser shows", "warning")
    return None
