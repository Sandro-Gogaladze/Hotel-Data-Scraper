"""
Anti-detection utilities for the Booking.com scraper.

This module provides functions to help avoid bot detection by rotating user agents,
adding random delays, and configuring browser settings to appear more human-like.
"""

import json
import os
import random
import time
from typing import Dict, Any, List
from utils.logger import log_message

def _bundled_chromium_major() -> str:
    """Major version of the Chromium build Playwright launches (e.g. "133"), read from
    Playwright's own browsers.json so it follows Playwright upgrades."""
    try:
        import playwright
        path = os.path.join(os.path.dirname(playwright.__file__), "driver", "package", "browsers.json")
        with open(path, encoding="utf-8") as f:
            for browser in json.load(f)["browsers"]:
                if browser["name"] == "chromium":
                    return browser["browserVersion"].split(".")[0]
    except Exception:
        pass
    return "133"  # Chromium bundled with the pinned playwright==1.50.0

CHROME_MAJOR_VERSION = _bundled_chromium_major()

# Chrome user agents matching the Chromium version actually running. Claiming an older
# Chrome, Firefox or Safari on a Chromium engine is an easy bot signal: sessions like that
# were sometimes served a cut-down room table (missing cheaper rates) or pages that never
# loaded, while sessions with a matching user agent got the same page as a normal visitor.
USER_AGENTS = [
    # Chrome on Windows
    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CHROME_MAJOR_VERSION}.0.0.0 Safari/537.36",
    # Chrome on macOS
    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CHROME_MAJOR_VERSION}.0.0.0 Safari/537.36",
]

def get_random_user_agent() -> str:
    """Get a random user agent string."""
    return random.choice(USER_AGENTS)

def add_random_delay(min_delay: float = 2.0, max_delay: float = 5.0) -> None:
    """Add a random delay between requests to appear more human-like."""
    delay = random.uniform(min_delay, max_delay)
    log_message(f"Adding random delay: {delay:.1f}s", "debug")
    time.sleep(delay)

def get_browser_launch_options(headless: bool = True, worker_id: int = 0) -> Dict[str, Any]:
    """
    Get browser launch options optimized for anti-detection.
    
    Args:
        headless (bool): Whether to run in headless mode
        worker_id (int): Worker ID for variation in settings
        
    Returns:
        Dict[str, Any]: Browser launch options
    """
    user_agent = get_random_user_agent()
    log_message(f"Worker #{worker_id} using user agent: {user_agent[:50]}...", "debug")
    
    # Comprehensive anti-detection arguments
    args = [
        '--disable-gpu',
        '--disable-dev-shm-usage', 
        '--disable-setuid-sandbox',
        '--no-sandbox',
        '--disable-accelerated-2d-canvas',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--disable-ipc-flooding-protection',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--disable-blink-features=AutomationControlled',
        '--disable-extensions',
        '--no-first-run',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-background-networking',
        '--disable-component-update',
        '--disable-client-side-phishing-detection',
        '--disable-hang-monitor',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-domain-reliability',
        '--disable-features=AudioServiceOutOfProcess',
        f'--user-agent={user_agent}'
    ]
    
    # Add worker-specific variation to avoid identical fingerprints
    if worker_id % 2 == 0:
        args.append('--disable-logging')
    if worker_id % 3 == 0:
        args.append('--disable-plugins')

    # Headed (local) and headless (GitHub Actions) runs use the same options apart from
    # the headless flag itself, so both see the same pages and produce the same data:
    # the full Chromium build in both modes (channel="chromium" runs it in the new
    # headless mode, instead of Playwright's separate chromium-headless-shell build),
    # identical args, and no slow_mo delays in headed mode.
    return {
        'headless': headless,
        'channel': 'chromium',
        'args': args,
    }

def configure_page_for_stealth(page) -> None:
    """
    Configure a page with stealth settings to avoid detection.
    
    Args:
        page: Playwright page object
    """
    # Remove webdriver property
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """)
    
    # Override the plugins property to use a custom getter
    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """)
    
    # Override the languages property to use a custom getter
    page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)
    
    # Override the permissions property
    page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        return window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)

def simulate_human_behavior(page) -> None:
    """
    Simulate human-like behavior on the page.
    
    Args:
        page: Playwright page object
    """
    try:
        # Random mouse movement
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.3, 0.8))
        
        # Random small scroll
        scroll_amount = random.randint(50, 200)
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.5, 1.2))
        
        log_message("Performed human-like behavior simulation", "debug")
    except Exception as e:
        log_message(f"Error in human behavior simulation: {e}", "debug")
