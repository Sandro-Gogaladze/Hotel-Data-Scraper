"""
Page navigation utilities for the Booking.com scraper - Optimized for speed.

This module provides helper functions to perform common navigation tasks
such as waiting for page loads, scrolling, clicking "Load More" buttons, and checking
for element existence.
"""

import os
import sys
import time
from typing import Tuple

# Ensure that the project root is in the system path for local imports.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from config import (
    SCROLL_DELAY, LOAD_MORE_TIMEOUT, LOAD_MORE_DELAY, LOAD_MORE_RETRIES,
    INITIAL_LOAD_DELAY, RETRY_COUNT, RETRY_DELAY
)
from playwright.sync_api import Page

LOAD_MORE_SELECTOR = "button:has-text('Load more results')"

def wait_for_initial_load(page: Page) -> None:
    """
    Wait for the initial page load by checking for specific elements.
    More efficient than a fixed delay.

    Args:
        page (Page): The Playwright page object.
    """
    log_message("Waiting for initial page content to load...", "debug")
    try:
        # Wait for the hotel cards to start appearing (initial batch)
        page.wait_for_selector("div[data-testid='property-card']", timeout=10000)
        # Give a very short delay for any initial dynamic content to finish loading
        time.sleep(0.5)  # Reduced from INITIAL_LOAD_DELAY to just 0.5 seconds
        log_message("Initial page content loaded", "debug")
    except Exception as e:
        log_message(f"Warning: Timeout waiting for initial content: {e}", "warning")
        # Fall back to a fixed delay if selector-based waiting fails
        time.sleep(INITIAL_LOAD_DELAY)

def scroll_to_bottom(page: Page) -> None:
    """
    Scroll to the bottom of the page.

    This function simulates a press of the "End" key and then waits for a short delay.

    Args:
        page (Page): The Playwright page object.
    """
    log_message("Scrolling to bottom of page", "debug")
    page.keyboard.press("End")
    time.sleep(SCROLL_DELAY)

def click_load_more_button(page: Page, current_count: int) -> Tuple[bool, int]:
    """
    Click the "Load more results" button and wait for new results to load.

    This function checks for the button's visibility, clicks it, and waits
    for the page's item count to increase.

    Args:
        page (Page): The Playwright page object.
        current_count (int): The current number of items loaded (used to verify if new items appear).

    Returns:
        Tuple[bool, int]: A tuple where the first element is a boolean indicating
        success (True if new items loaded), and the second element is the new count.
    """
    load_more_btn = page.locator(LOAD_MORE_SELECTOR)
    
    if not load_more_btn.is_visible():
        log_message("No 'Load More Results' button found", "debug")
        return False, current_count
    
    try:
        # Wait for the button to become visible.
        load_more_btn.wait_for(state="visible", timeout=LOAD_MORE_TIMEOUT)
        log_message("Found 'Load More Results' button, clicking...", "info")

        # Dismiss any transient overlay (e.g. a sign-in/Genius nudge popup) that may
        # be sitting on top of the button before we try to click it.
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        # Click the button. Give it a short explicit timeout rather than inheriting
        # the page's full default timeout, and fall back to a force click if a
        # transient overlay is still intercepting pointer events at that position -
        # we've already confirmed the button itself is visible/enabled/stable above.
        try:
            load_more_btn.click(timeout=5000)
        except Exception as click_error:
            log_message(f"Normal click intercepted ({click_error}), retrying with force click", "debug")
            load_more_btn.click(force=True, timeout=5000)
        time.sleep(LOAD_MORE_DELAY)
        
        # More efficient check for new items - check every 0.5 second up to 15 times
        # (this is faster than waiting 30 seconds like in the original)
        for wait_iter in range(15):
            new_count = len(page.locator("div[data-testid='title']").all())
            if new_count > current_count:
                log_message(f"Successfully loaded more items: {current_count} -> {new_count}", "info")
                return True, new_count
            time.sleep(0.5)  # Reduced from 1 second to 0.5 second
        
        log_message("No new items were loaded after clicking", "warning")
        return False, current_count
    
    except Exception as e:
        log_message(f"Error clicking 'Load More Results': {e}", "warning")
        return False, current_count

def load_all_items(page: Page, selector: str = "div[data-testid='property-card']") -> int:
    """
    Load all items on the page using adaptive scrolling for maximum performance.

    Args:
        page (Page): The Playwright page object.
        selector (str): The CSS selector to use for counting the loaded items.

    Returns:
        int: The final count of items loaded on the page.
    """
    log_message("Starting optimized content loading process", "info")
    start_time = time.time()
    
    previous_count = 0
    scroll_count = 0
    no_change_count = 0
    max_no_change = 3  # Maximum number of scrolls with no new items before trying "Load more"
    
    # Fast initial scrolling to get most content loaded quickly
    log_message("Performing initial rapid scrolling", "debug")
    for _ in range(5):  # Do 5 quick scrolls to get most content
        page.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")  # Scroll 1.5x viewport height
        time.sleep(0.3)  # Very short delay between rapid scrolls
    
    # Adaptive scrolling algorithm with dynamic delays
    while True:
        # Scroll to different positions based on scroll count
        if scroll_count % 3 == 0:
            # Every 3rd scroll, go all the way to the bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            # Other scrolls, move down by 2x viewport height
            page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        
        scroll_count += 1
        
        # Dynamic sleep - shorter if we're getting new items consistently, longer if not
        sleep_time = 0.3 if no_change_count == 0 else 0.7
        time.sleep(sleep_time)
        
        # Count the number of items matching the given selector.
        current_count = len(page.locator(selector).all())
        
        # Log progress every few scrolls
        if scroll_count % 3 == 0 or current_count != previous_count:
            elapsed = time.time() - start_time
            log_message(f"Scroll #{scroll_count}: Loaded {current_count} items in {elapsed:.1f}s", "info")
        
        # Check if we've reached the end (no new items after several scrolls)
        if current_count == previous_count:
            no_change_count += 1
            
            # After a few scrolls with no new items, try the load more button
            if no_change_count >= max_no_change:
                # Try clicking the "Load more" button
                button_success, new_count = click_load_more_button(page, current_count)

                # A slow response can outlast click_load_more_button's wait even though
                # more results exist (Sept 2026: one search stopped at 646 of ~800). The
                # button is gone at the true end of the list, so retry while it's shown.
                retries = 0
                while not button_success and retries < LOAD_MORE_RETRIES:
                    late_count = len(page.locator(selector).all())
                    if late_count > current_count:
                        button_success, new_count = True, late_count
                        break
                    if not page.locator(LOAD_MORE_SELECTOR).is_visible():
                        break
                    retries += 1
                    log_message(f"'Load more' loaded nothing new, retrying ({retries}/{LOAD_MORE_RETRIES})", "warning")
                    button_success, new_count = click_load_more_button(page, current_count)

                if button_success:
                    current_count = new_count
                    no_change_count = 0  # Reset the counter if we got new items
                else:
                    # If button didn't work and we still have no new items, we're done
                    elapsed = time.time() - start_time
                    log_message(f"All items fully loaded! Total: {current_count} in {elapsed:.1f}s", "info")
                    log_message(f"Average time per hotel: {elapsed/current_count:.2f}s", "info")
                    break
        else:
            # If we got new items, reset the no_change counter
            no_change_count = 0
        
        # Update the count for the next iteration.
        previous_count = current_count
    
    return current_count

def wait_for_selector(page: Page, selector: str, timeout: int, description: str = "element") -> bool:
    """
    Wait for a specific selector to appear on the page.

    Args:
        page (Page): The Playwright page object.
        selector (str): CSS selector of the element to wait for.
        timeout (int): The timeout in milliseconds.
        description (str): A human-readable description of the element (for logging).

    Returns:
        bool: True if the element appears before timeout; False otherwise.
    """
    try:
        log_message(f"Waiting for {description} ({selector})", "debug")
        page.wait_for_selector(selector, timeout=timeout)
        log_message(f"Found {description}", "debug")
        return True
    except Exception as e:
        log_message(f"Timed out waiting for {description}: {e}", "warning")
        return False

def check_element_exists(page: Page, selector: str, description: str = "element") -> bool:
    """
    Check if an element exists on the page without waiting.

    Args:
        page (Page): The Playwright page object.
        selector (str): CSS selector of the element.
        description (str): A human-readable description of the element (for logging).

    Returns:
        bool: True if the element exists, False otherwise.
    """
    try:
        element = page.query_selector(selector)
        exists = element is not None
        log_message(f"Check for {description}: {'Found' if exists else 'Not found'}", "debug")
        return exists
    except Exception as e:
        log_message(f"Error checking for {description}: {e}", "warning")
        return False