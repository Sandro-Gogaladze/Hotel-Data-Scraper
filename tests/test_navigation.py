"""
Tests for browser/navigation.py's pagination loop, run against a local page in real
headless Chromium. Sleeps are patched out: the fake "Load more" handler is synchronous,
so there's nothing to wait for.
"""

import browser.navigation as navigation

CARD = '<div data-testid="property-card"><div data-testid="title">Hotel {n}</div></div>'

# First click loads nothing (a response slower than the post-click wait); the second
# click appends two cards and removes the button, like the real end of the list.
SLOW_LOAD_MORE_PAGE = f"""
<div id="list">{CARD.format(n=1)}{CARD.format(n=2)}</div>
<button id="more">Load more results</button>
<script>
  let clicks = 0;
  document.getElementById('more').addEventListener('click', (e) => {{
    clicks += 1;
    if (clicks < 2) return;
    document.getElementById('list').insertAdjacentHTML('beforeend', `{CARD.format(n=3)}{CARD.format(n=4)}`);
    e.target.remove();
  }});
</script>
"""


def test_load_all_items_retries_when_load_more_loads_nothing(page, monkeypatch):
    monkeypatch.setattr(navigation.time, "sleep", lambda s: None)
    page.set_content(SLOW_LOAD_MORE_PAGE)

    assert navigation.load_all_items(page) == 4


def test_load_all_items_stops_when_button_is_gone(page, monkeypatch):
    monkeypatch.setattr(navigation.time, "sleep", lambda s: None)
    page.set_content(f"<div>{CARD.format(n=1)}{CARD.format(n=2)}</div>")

    assert navigation.load_all_items(page) == 2
