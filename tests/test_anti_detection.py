from utils.anti_detection import (
    USER_AGENTS,
    get_browser_launch_options,
    get_random_user_agent,
)


def test_get_random_user_agent_returns_known_agent():
    assert get_random_user_agent() in USER_AGENTS


def test_launch_options_basic_structure():
    options = get_browser_launch_options(headless=True, worker_id=1)

    assert options["headless"] is True
    assert isinstance(options["args"], list)
    assert any(arg.startswith("--user-agent=") for arg in options["args"])


def test_launch_options_headless_adds_headless_only_flags():
    options = get_browser_launch_options(headless=True, worker_id=1)

    assert "--disable-dev-tools" in options["args"]
    assert "--mute-audio" in options["args"]
    # headed mode should not carry these
    assert "slow_mo" not in options


def test_launch_options_headed_sets_slow_mo():
    options = get_browser_launch_options(headless=False, worker_id=2)

    assert "slow_mo" in options
    assert options["slow_mo"] == 50 + (2 * 10)
    assert "--disable-dev-tools" not in options["args"]


def test_launch_options_worker_variation():
    # worker_id 0: divisible by both 2 and 3 -> both extra flags present
    options_0 = get_browser_launch_options(headless=True, worker_id=0)
    assert "--disable-logging" in options_0["args"]
    assert "--disable-plugins" in options_0["args"]

    # worker_id 1: divisible by neither -> neither flag present
    options_1 = get_browser_launch_options(headless=True, worker_id=1)
    assert "--disable-logging" not in options_1["args"]
    assert "--disable-plugins" not in options_1["args"]
