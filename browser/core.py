"""
Core browser functionality for the Booking.com scraper.

This module provides helper functions to create and close browser pages.
Optimized for speed by using more efficient browser settings.
"""

import os
import sys
from typing import Optional, Dict, Any

# Ensure that the project root is in the PYTHONPATH so that local imports work,
# regardless of the current working directory.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from utils.anti_detection import configure_page_for_stealth, get_random_user_agent
from config import PAGE_LOAD_TIMEOUT
from playwright.sync_api import Browser, Page

def create_new_page(browser: Browser, url: Optional[str] = None, timeout: int = PAGE_LOAD_TIMEOUT,
                    storage_state: Optional[Dict[str, Any]] = None) -> Page:
    """
    Create a new browser page and optionally navigate to a given URL.

    Args:
        browser (Browser): A Playwright Browser instance.
        url (Optional[str]): URL to navigate to. If None, no navigation is performed.
        timeout (int): Navigation timeout in milliseconds. Defaults to PAGE_LOAD_TIMEOUT.
        storage_state (Optional[Dict[str, Any]]): Cookies of the run's pinned session
            (see scraper/session.py), or None for a fresh session.

    Returns:
        Page: The newly created Playwright page object.
    """
    log_message("Creating new browser page with anti-detection", "debug")

    # Each page gets its own context so it can carry the run's session cookies
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},  # Standard desktop viewport
        storage_state=storage_state,
    )
    page: Page = context.new_page()
    
    # Configure anti-detection measures
    configure_page_for_stealth(page)
    
    # Optimize page settings for speed and stealth
    page.set_default_timeout(timeout)
    
    # Configure page for faster performance by blocking non-essential resources
    # But be less aggressive to avoid detection
    page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}", lambda route: route.abort())
    page.route("**/*analytics*.js", lambda route: route.abort())
    page.route("**/*tracker*.js", lambda route: route.abort())
    page.route("**/*advertisement*.js", lambda route: route.abort())
    page.route("**/*google*.js", lambda route: route.abort())
    
    # Disable CSS animations and transitions for better performance
    page.add_style_tag(content="""
        * {
            animation: none !important;
            transition: none !important;
        }
    """)
    
    # If a URL is provided, navigate to that URL with the specified timeout.
    if url:
        log_message(f"Navigating to URL: {url}", "debug")
        try:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")  # Changed from default "load" to faster "domcontentloaded"
            log_message(f"Successfully loaded URL: {url}", "debug")
        except Exception as e:
            log_message(f"Error loading URL {url}: {e}", "error")
            # Don't raise - allow the calling code to handle navigation failures
    
    return page

def close_page(page: Page) -> None:
    """
    Safely close a Playwright browser page.

    Args:
        page (Page): The Playwright Page object to close.
    """
    try:
        if page:
            log_message("Closing browser page", "debug")
            page.context.close()  # create_new_page gives every page its own context
    except Exception as e:
        log_message(f"Error closing page: {e}", "warning")