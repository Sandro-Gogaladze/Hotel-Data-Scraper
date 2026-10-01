"""
Tests for scraper/session.py: picking a visitor session that gets the full room table.

Booking.com assigns each new session a page version at random, so these serve local
fixtures through Playwright routing: the fake "site" hands out a given sequence of
room-table versions, one per new session.
"""

from conftest import load_fixture

from scraper.session import establish_session, room_table_version

SEARCH_URL = "https://www.booking.com/searchresults.html?ss=Borjomi&selected_currency=GEL"
FULL = load_fixture("hotel_detail_rooms.html")          # per-row occupancy column
REDUCED = load_fixture("hotel_detail_rooms_sleeps.html")  # "Sleeps: N adults" per room type


class FakeSite:
    """Wraps a real browser; each new context gets the next room-table version."""

    def __init__(self, browser, versions):
        self.browser = browser
        self.versions = list(versions)
        self.contexts = 0

    def new_context(self, **kwargs):
        self.contexts += 1
        version = self.versions.pop(0)  # one html for every hotel, or {hotel slug: html}
        context = self.browser.new_context(**kwargs)
        context.route("**/searchresults*", lambda route: route.fulfill(
            body=load_fixture("search_results.html"), content_type="text/html"))

        def hotel(route):
            slug = route.request.url.split("/hotel/ge/")[1].split(".")[0]
            html = version.get(slug, "<p>We have no availability</p>") if isinstance(version, dict) else version
            route.fulfill(body=html, content_type="text/html",
                          headers={"Set-Cookie": "bkng=session-%d; Path=/" % self.contexts})

        context.route("**/hotel/**", hotel)
        return context


def test_room_table_version(page):
    page.set_content(FULL)
    assert room_table_version(page) == "full"
    page.set_content(REDUCED)
    assert room_table_version(page) == "reduced"
    page.set_content("<p>We have no availability here</p>")
    assert room_table_version(page) is None


def test_establish_session_retries_until_full_table(browser):
    site = FakeSite(browser, [REDUCED, REDUCED, FULL, FULL])

    state = establish_session(site, SEARCH_URL, attempts=5)

    assert site.contexts == 3
    # the returned cookies are the full-table session's, ready for new_context(storage_state=...)
    assert {"name": "bkng", "value": "session-3"} in [
        {"name": c["name"], "value": c["value"]} for c in state["cookies"]]


def test_property_that_always_uses_sleeps_table_does_not_reject_a_full_session(browser):
    # Some hotels show the "Sleeps" table even in a full session; a later hotel on the
    # same session showing the full table proves the session is fine.
    site = FakeSite(browser, [{"frida": REDUCED, "kazbegi-estate": FULL}])

    assert establish_session(site, SEARCH_URL, attempts=1) is not None
    assert site.contexts == 1


def test_establish_session_gives_up_after_attempts(browser):
    site = FakeSite(browser, [REDUCED] * 3)

    assert establish_session(site, SEARCH_URL, attempts=3) is None
    assert site.contexts == 3
