"""
Anti-detection utilities for the Booking.com scraper.

This module provides functions to help avoid bot detection by rotating user agents,
adding random delays, and configuring browser settings to appear more human-like.
"""

import random
import time
from typing import Dict, Any, List
from utils.logger import log_message

# Modern, realistic user agents
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on macOS  
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.77"
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
    
    # Additional args for headless mode
    if headless:
        args.extend([
            '--disable-dev-tools',
            '--mute-audio'
        ])
        # Vary image loading by worker to create different fingerprints
        if worker_id % 2 == 0:
            args.append('--disable-images')
    
    launch_options = {
        'headless': headless,
        'args': args
    }
    
    # Only add slow_mo when not headless (for debugging)
    if not headless:
        launch_options['slow_mo'] = 50 + (worker_id * 10)  # Vary slow_mo by worker
        
    return launch_options

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
