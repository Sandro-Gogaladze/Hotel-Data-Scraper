"""
Functions for extracting basic data from the Booking.com search results page.

This module opens the search page using Playwright, waits for all hotel elements to load,
and then extracts basic information (e.g., hotel name, link, address, price, and review info)
from each hotel card.
"""

import os
import sys
import time
from typing import Any, List, Dict

# Ensure the project root is in sys.path regardless of the current working directory.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from browser.core import create_new_page, close_page
from browser.navigation import wait_for_initial_load, load_all_items
from scraper.search_page.locators import HOTEL_CARD
from scraper.search_page.extractor import extract_hotel_basic_info, get_all_hotel_elements, batch_extract_basic_info

def extract_basic_info(browser: Any, url: str) -> List[Dict[str, Any]]:
    """
    Open the Booking.com search page, wait for all hotel results to load,
    and extract basic information for each hotel.

    This function creates a new page using the provided browser instance,
    waits for the initial load and subsequent loading of all hotel elements,
    then uses helper functions to retrieve the basic details of each hotel card.

    Args:
        browser (Any): A Playwright browser instance.
        url (str): The URL of the Booking.com search results page.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing basic hotel data.
    """
    # Start timing the extraction
    extraction_start_time = time.time()
    
    # Open a new page and navigate to the search results URL.
    page = create_new_page(browser, url)
    log_message(f"Navigated to search page: {url}", "info")
    
    # Wait for the initial page load and then load all hotel items (using infinite scroll logic).
    wait_for_initial_load(page)
    log_message("Starting to load all hotel items...", "info")
    total_hotels = load_all_items(page, HOTEL_CARD)
    log_message(f"All {total_hotels} hotel cards loaded, now extracting data", "info")
    
    # Use optimized extraction method that combines all operations in a single JS execution
    try:
        basic_hotels = batch_extract_basic_info(page)
        if not basic_hotels:
            raise Exception("JS extraction returned no results")
    except Exception as e:
        log_message(f"JS extraction failed: {e}, falling back to DOM method", "warning")
        hotel_elements = get_all_hotel_elements(page)
        basic_hotels = [extract_hotel_basic_info(hotel, idx) for idx, hotel in enumerate(hotel_elements)]
    
    # Close the page since we no longer need it
    close_page(page)
    
    extraction_time = time.time() - extraction_start_time
    log_message(f"✅ Extracted basic info for {len(basic_hotels)} hotels in {extraction_time:.2f} seconds", "info")
    log_message(f"Average time per hotel: {extraction_time/len(basic_hotels):.2f} seconds", "info")
    
    return basic_hotels
