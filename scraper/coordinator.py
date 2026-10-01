"""
Main coordinator module for the Booking.com scraper.

This module orchestrates the entire scraping process, including:
1. Extracting basic hotel information from the search results page
2. Processing hotel details in parallel using multiple processes
3. Saving the results to CSV files
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, List, Dict

# Ensure that the project root is added to sys.path for correct module resolution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from utils.url_parser import propagate_search_params
from scraper.search_page.basic_extractor import extract_basic_info
from scraper.session import establish_session
from scraper.hotel_page.process_based_extractor import process_all_details_processes
from config import HEADLESS  # Import HEADLESS from config

def pin_hotel_link_params(hotels: List[Dict[str, Any]], search_url: str) -> None:
    """Make each hotel page use the search's currency and language, so room prices match
    the search page and star ratings are shown (see propagate_search_params)."""
    for hotel in hotels:
        hotel["Hotel Link"] = propagate_search_params(search_url, hotel.get("Hotel Link", "N/A"))

def display_progress_estimate(start_time: float, total_hotels: int, processed_hotels: int) -> None:
    """
    Display progress and estimated time remaining.
    
    Args:
        start_time (float): Time when the process started.
        total_hotels (int): Total number of hotels to process.
        processed_hotels (int): Number of hotels processed so far.
    """
    if processed_hotels == 0:
        return
    
    elapsed_time = time.time() - start_time
    time_per_hotel = elapsed_time / processed_hotels
    remaining_hotels = total_hotels - processed_hotels
    estimated_remaining_time = remaining_hotels * time_per_hotel
    
    progress_percent = (processed_hotels / total_hotels) * 100
    
    # Format the remaining time
    remaining_hours = int(estimated_remaining_time // 3600)
    remaining_minutes = int((estimated_remaining_time % 3600) // 60)
    remaining_seconds = int(estimated_remaining_time % 60)
    
    if remaining_hours > 0:
        time_str = f"{remaining_hours}h {remaining_minutes}m {remaining_seconds}s"
    elif remaining_minutes > 0:
        time_str = f"{remaining_minutes}m {remaining_seconds}s"
    else:
        time_str = f"{remaining_seconds}s"
    
    log_message(f"Progress: {processed_hotels}/{total_hotels} hotels ({progress_percent:.1f}%)", "info")
    log_message(f"Estimated time remaining: {time_str}", "info")

def process_booking_search(browser: Any, url: str) -> List[Dict[str, Any]]:
    """
    Process a Booking.com search page to extract hotel information.

    Args:
        browser (Any): A Playwright browser instance
        url (str): The URL of the Booking.com search results page.

    Returns:
        List[Dict[str, Any]]: List of hotel data dictionaries
    """
    # Start a timer to measure the total execution time.
    start_time = time.time()
    log_message(f"Starting scraping process at: {time.strftime('%H:%M:%S')}", "info")
    log_message(f"Browser headless mode: {'Enabled' if HEADLESS else 'Disabled'}", "info")
    
    # Phase 1: Extract basic hotel information from the search results page.
    log_message("🔍 Phase 1: Extracting basic hotel information from search page", "info")
    
    # Pin one visitor session for the whole run so every page sees the same site version
    session_state = establish_session(browser, url)
    basic_hotels = extract_basic_info(browser, url, storage_state=session_state)
    
    # Check if any hotels were found.
    if not basic_hotels:
        log_message("❌ No hotels found. Check the URL or try again later.", "error")
        return []
    
    log_message(f"Found {len(basic_hotels)} hotels on search page", "info")
    pin_hotel_link_params(basic_hotels, url)

    # Phase 2: Process hotel details in parallel using multiple processes.
    log_message(f"🔍 Phase 2: Extracting detailed information for {len(basic_hotels)} hotels", "info")
    detailed_hotels = process_all_details_processes(basic_hotels, storage_state=session_state)
    
    # Calculate and log the total execution time.
    end_time = time.time()
    execution_time = end_time - start_time
    log_message(f"✅ Scraping completed in {execution_time:.2f} seconds", "info")
    
    return detailed_hotels

def process_booking_search_with_progress(browser: Any, url: str, progress_callback=None) -> List[Dict[str, Any]]:
    """
    Process a Booking.com search page to extract hotel information with progress tracking.

    Args:
        browser (Any): A Playwright browser instance
        url (str): The URL of the Booking.com search results page.
        progress_callback (callable): Optional callback function for progress updates
                                    Called with (total=int) and (current=int) parameters

    Returns:
        List[Dict[str, Any]]: List of hotel data dictionaries
    """
    # Start a timer to measure the total execution time.
    start_time = time.time()
    log_message(f"Starting scraping process at: {time.strftime('%H:%M:%S')}", "info")
    log_message(f"Browser headless mode: {'Enabled' if HEADLESS else 'Disabled'}", "info")
    
    # Phase 1: Extract basic hotel information from the search results page.
    log_message("🔍 Phase 1: Extracting basic hotel information from search page", "info")
    
    # Pin one visitor session for the whole run so every page sees the same site version
    session_state = establish_session(browser, url)
    basic_hotels = extract_basic_info(browser, url, storage_state=session_state)
    
    # Check if any hotels were found.
    if not basic_hotels:
        log_message("❌ No hotels found. Check the URL or try again later.", "error")
        if progress_callback:
            progress_callback(total=0, current=0)
        return []
    
    log_message(f"Found {len(basic_hotels)} hotels on search page", "info")
    pin_hotel_link_params(basic_hotels, url)

    # Update progress with total count
    if progress_callback:
        progress_callback(total=len(basic_hotels))
    
    # Phase 2: Process hotel details in parallel using multiple processes.
    log_message(f"🔍 Phase 2: Extracting detailed information for {len(basic_hotels)} hotels", "info")
    
    # We need to modify the process_all_details_processes function to accept progress callback
    # For now, let's import and use the modified version
    from scraper.hotel_page.process_based_extractor import process_all_details_processes_with_progress
    detailed_hotels = process_all_details_processes_with_progress(basic_hotels, progress_callback, storage_state=session_state)
    
    # Calculate and log the total execution time.
    end_time = time.time()
    execution_time = end_time - start_time
    log_message(f"✅ Scraping completed in {execution_time:.2f} seconds", "info")
    
    return detailed_hotels