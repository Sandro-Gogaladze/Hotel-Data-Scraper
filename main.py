#!/usr/bin/env python3
"""
Booking.com Scraper - Main Entry Point

This script orchestrates the Booking.com scraper with optimizations for speed
and improved logging focused on showing scraped data. It uses an improved extraction 
logic directly integrated from the filling module for more reliable results.
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, List, Dict

# Ensure that the script's directory is in sys.path for local imports.
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from playwright.sync_api import sync_playwright  # type: ignore

from config import OUTPUT_DIR, HEADLESS  
from utils.logger import log_message
from utils.anti_detection import get_browser_launch_options, add_random_delay
from scraper.coordinator import process_booking_search
from export.excel import save_to_excel  # Import the Excel export function instead of CSV

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

def main() -> None:
    """
    Main function to run the Booking.com scraper.

    It prompts for the URL, creates an output file based on the current date,
    launches the scraper through Playwright with speed optimizations to extract 
    hotel data, and writes the output to Excel.
    """
    log_message("🚀 Starting Booking.com scraper...", "info")
    
    # Get the Booking.com search URL from the user.
    url: str = input("Enter the Booking.com URL: ").strip()
    if not url.startswith("https://www.booking.com/"):
        log_message("❌ Invalid URL! Please enter a valid Booking.com search URL.", "error")
        return
    
    # Prepare the output file path.
    today_date: str = datetime.today().strftime("%Y-%m-%d")
    timestamp: str = datetime.now().strftime("%H-%M-%S")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file: str = f"{OUTPUT_DIR}/{today_date}_{timestamp}.xlsx"  # Use xlsx extension

    # Launch Playwright and use the scraper to extract hotel data.
    start_time = time.time()
    log_message(f"Starting scraping process at: {datetime.now().strftime('%H:%M:%S')}", "info")
    
    with sync_playwright() as p:
        # Use anti-detection browser options for main browser
        launch_options = get_browser_launch_options(headless=HEADLESS, worker_id=0)
        browser: Any = p.chromium.launch(**launch_options)
        
        try:
            # Add random delay before starting to appear more human
            add_random_delay(1.0, 3.0)
            
            hotels_data = process_booking_search(browser, url)
            basic_phase_end_time = time.time()
            basic_duration = basic_phase_end_time - start_time
            log_message(f"Scraping completed in {basic_duration:.2f} seconds", "info")
            
            # Calculate and log the total time taken
            end_time = time.time()
            duration = end_time - start_time
            log_message(f"Total process completed in {duration:.2f} seconds", "info")
            
            # Save results if we have data - using Excel now and pass the search URL and duration
            if hotels_data:
                save_to_excel(hotels_data, output_file, search_url=url, duration_seconds=duration)
                log_message(f"✅ Excel file created: {output_file}", "info")
            else:
                log_message("❌ No hotel data was collected.", "error")
            
        except Exception as e:
            log_message(f"❌ Error during scraping: {e}", "error")
            # Calculate duration even for emergency save
            end_time = time.time()
            duration = end_time - start_time
            # Try to save whatever data we have - using Excel now
            if 'hotels_data' in locals() and hotels_data:
                emergency_file = f"{os.path.splitext(output_file)[0]}_emergency.xlsx"  # Use xlsx extension
                save_to_excel(hotels_data, emergency_file, search_url=url, duration_seconds=duration)  # Pass duration here too
                log_message(f"Saved emergency data to {emergency_file}", "info")
            browser.close()
            return
        browser.close()
    
    # Log the total time already calculated above, no need to recalculate
    log_message("✅ DONE!", "info")
    
    # Keep the script running until manually terminated.
    print("\nPress Ctrl+C to exit...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()