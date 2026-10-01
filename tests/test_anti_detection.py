from utils.anti_detection import (
    USER_AGENTS,
    get_browser_launch_options,
    get_random_user_agent,
)


def test_get_random_user_agent_returns_known_agent():
    assert get_random_user_agent() in USER_AGENTS


def test_user_agents_match_the_chromium_actually_launched():
    """A UA that disagrees with the real engine (old Chrome, Firefox, Safari) gets
    degraded pages from booking.com, so every UA must claim the bundled Chromium version."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        major = browser.version.split(".")[0]
        browser.close()

    for ua in USER_AGENTS:
        assert f"Chrome/{major}.0.0.0" in ua
        assert "Firefox" not in ua and "Version/" not in ua


def test_launch_options_basic_structure():
    options = get_browser_launch_options(headless=True, worker_id=1)

    assert options["headless"] is True
    assert isinstance(options["args"], list)
    assert any(arg.startswith("--user-agent=") for arg in options["args"])


def test_headed_and_headless_launch_the_same_browser_the_same_way():
    """Local runs are headed and GitHub Actions runs are headless; nothing else may
    differ, so both produce the same data."""
    for worker_id in range(6):
        headless = get_browser_launch_options(headless=True, worker_id=worker_id)
        headed = get_browser_launch_options(headless=False, worker_id=worker_id)

        assert headless.pop("headless") is True and headed.pop("headless") is False
        # the user agent is picked at random per launch; compare everything else
        strip_ua = lambda o: {**o, "args": [a for a in o["args"] if not a.startswith("--user-agent=")]}
        assert strip_ua(headless) == strip_ua(headed)
        assert headed["channel"] == "chromium"  # full Chromium build, not the headless shell
        assert "slow_mo" not in headed


def test_launch_options_worker_variation():
    # worker_id 0: divisible by both 2 and 3 -> both extra flags present
    options_0 = get_browser_launch_options(headless=True, worker_id=0)
    assert "--disable-logging" in options_0["args"]
    assert "--disable-plugins" in options_0["args"]

    # worker_id 1: divisible by neither -> neither flag present
    options_1 = get_browser_launch_options(headless=True, worker_id=1)
    assert "--disable-logging" not in options_1["args"]
    assert "--disable-plugins" not in options_1["args"]
