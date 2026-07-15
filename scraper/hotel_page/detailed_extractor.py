"""
Detailed Extractor for Booking.com Hotel Details

This module is responsible for extracting detailed room-level information from a hotel's detail page.
Using a Playwright browser instance and a hotel data dictionary (with basic info such as "Hotel Name", 
"Hotel Link", and an optional "Index" for numbering), it opens the hotel's detail page, extracts the required
information using the core extraction function (extract_hotel_detailed_info), and merges the extracted data
into the original hotel_data dictionary.
"""

import os
import sys
import time
import re
from typing import Dict, Any, List, Optional

# Ensure the project root is included in sys.path for proper module resolution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from browser.core import create_new_page, close_page
from playwright.sync_api import sync_playwright
from config import HEADLESS, HOTEL_WAIT_TIMEOUT, INITIAL_NAVIGATION_TIMEOUT, URL_LOADING_REFRESH_TIMEOUT
from analyzers.breakfast import analyze_breakfast_with_gpt4
from scraper.hotel_page.locators import (
    ROOM_ROW, ROOM_PRICE_ATTRIBUTE, OCCUPANCY_ICON, NO_AVAILABILITY,
    FREE_CANCELLATION_JS, NON_REFUNDABLE_JS, HAS_BREAKFAST_JS,
    BREAKFAST_TEXT_JS, MAX_PERSONS_JS
)

def extract_room_details(row: Any, hotel_name: str, room_index: int) -> Optional[Dict[str, Any]]:
    """
    Extract details from a room row on a hotel detail page.
    
    Args:
        row: The Playwright element representing a room row.
        hotel_name (str): The name of the hotel (for logging purposes).
        room_index (int): The index of the room in the list (for logging).
        
    Returns:
        Optional[Dict[str, Any]]: A dictionary with room details, or None if extraction fails.
    """
    # Only log at debug level, not info
    log_message(f"Extracting details for room #{room_index + 1} at {hotel_name}", "debug")
    room_details: Dict[str, Any] = {}

    # --- Extract the price using the ROOM_PRICE_ATTRIBUTE ---
    price_str: str = row.get_attribute(ROOM_PRICE_ATTRIBUTE) or ""
    try:
        # Clean the price string and convert it to an integer.
        room_details["price"] = int(price_str.strip())
    except Exception as e:
        log_message(f"Could not convert price '{price_str}' to int: {e}", "debug")
        return None

    # --- Extract maximum occupancy: either via screen reader text or occupancy icons ---
    try:
        sr_only_text = row.evaluate(MAX_PERSONS_JS)
        match = re.search(r"Max persons:\s*(\d+)", sr_only_text)
        if match:
            max_persons = int(match.group(1))
        else:
            person_icons = row.query_selector_all(OCCUPANCY_ICON)
            max_persons = len(person_icons) if person_icons else None
        room_details["max_persons"] = max_persons
    except Exception as e:
        log_message(f"Error extracting max persons for room #{room_index + 1}: {e}", "debug")
        room_details["max_persons"] = None

    # --- Check for free cancellation information ---
    try:
        fc_text = row.evaluate(FREE_CANCELLATION_JS)
        room_details["free_cancellation"] = "Free cancellation" in fc_text
    except Exception as e:
        log_message(f"Error checking free cancellation for room #{room_index + 1}: {e}", "debug")
        room_details["free_cancellation"] = False

    # --- Check for non-refundable policy ---
    try:
        nr_text = row.evaluate(NON_REFUNDABLE_JS)
        non_ref_phrases = ["non-refundable", "non refundable", "no refund"]
        # Check if any of the keywords appear in the text.
        room_details["non_refundable"] = any(phrase in nr_text.lower() for phrase in non_ref_phrases)
    except Exception as e:
        log_message(f"Error checking non-refundable for room #{room_index + 1}: {e}", "debug")
        room_details["non_refundable"] = False

    # --- Initialize breakfast fields ---
    room_details["breakfast_included"] = False
    room_details["has_breakfast_mention"] = False
    room_details["breakfast_text"] = ""

    # --- Check if breakfast is mentioned ---
    try:
        has_breakfast = row.evaluate(HAS_BREAKFAST_JS)
        room_details["has_breakfast_mention"] = has_breakfast
        if has_breakfast:
            # Retrieve the full breakfast description text.
            room_details["breakfast_text"] = row.evaluate(BREAKFAST_TEXT_JS)
    except Exception as e:
        log_message(f"Error checking breakfast mention for room #{room_index + 1}: {e}", "debug")

    # Don't log individual room details, we'll summarize later
    return room_details

def analyze_rooms(rooms: List[Dict[str, Any]], hotel_name: str) -> Dict[str, Any]:
    """
    Analyze room details to determine the minimum price room overall and for 2-person occupancy,
    including analyzing whether breakfast is included for free.
    
    Args:
        rooms (List[Dict[str, Any]]): A list of dictionaries, each containing details for a room.
        hotel_name (str): The name of the hotel (for logging purposes).
        
    Returns:
        Dict[str, Any]: A dictionary with keys for different minimum price and room feature details.
    """
    result: Dict[str, Any] = {
        "Min Room Price": "N/A",
        "Min Room Price Free Cancellation": "N/A",
        "Min Room Price Non-refundable": "N/A",
        "Min Room Price Breakfast Included": "N/A",
        "Min 2 Person Price": "N/A",
        "Min 2 Person Price Free Cancellation": "N/A",
        "Min 2 Person Price Non-refundable": "N/A",
        "Min 2 Person Price Breakfast Included": "N/A"
    }
    
    if not rooms:
        log_message(f"No rooms found for {hotel_name}", "warning")
        return result
    
    # Log a summary of the rooms found instead of individual details
    log_message(f"Analyzing {len(rooms)} rooms for {hotel_name}", "info")
    price_summary = [f"${room['price']}" for room in rooms[:5]]  # Show up to 5 prices as a sample
    if len(rooms) > 5:
        price_summary.append(f"... and {len(rooms) - 5} more")
    log_message(f"Room prices: {', '.join(price_summary)}", "info")
    
    # --- Determine the room with the minimum price overall.
    min_price_overall = min(rooms, key=lambda r: r["price"])
    log_message(f"Found minimum price room overall: ${min_price_overall['price']}", "info")
    
    # --- Filter rooms that can accommodate 2 persons ---
    two_person_rooms = [r for r in rooms if r.get("max_persons") == 2]
    log_message(f"Found {len(two_person_rooms)} 2-person rooms", "info")
    
    min_price_2person = None
    if two_person_rooms:
        min_price_2person = min(two_person_rooms, key=lambda r: r["price"])
        log_message(f"Found minimum price 2-person room: ${min_price_2person['price']}", "info")
    
    # --- Use GPT-4 to determine whether breakfast is included for free ---
    if min_price_overall["has_breakfast_mention"]:
        min_price_overall["breakfast_included"] = analyze_breakfast_with_gpt4(
            min_price_overall["breakfast_text"]
        )
        log_message(f"Breakfast included in min price room: {min_price_overall['breakfast_included']}", "info")

    if min_price_2person and min_price_2person["has_breakfast_mention"]:
        # Only analyze if the 2-person room is different from the overall min price room
        if min_price_2person is not min_price_overall:
            min_price_2person["breakfast_included"] = analyze_breakfast_with_gpt4(
                min_price_2person["breakfast_text"]
            )
            log_message(f"Breakfast included in min 2-person room: {min_price_2person['breakfast_included']}", "info")
    
    # --- Populate result using the chosen room details ---
    result["Min Room Price"] = min_price_overall["price"]
    result["Min Room Price Free Cancellation"] = min_price_overall["free_cancellation"]
    result["Min Room Price Non-refundable"] = min_price_overall["non_refundable"]
    result["Min Room Price Breakfast Included"] = min_price_overall["breakfast_included"]
    
    if min_price_2person:
        result["Min 2 Person Price"] = min_price_2person["price"]
        result["Min 2 Person Price Free Cancellation"] = min_price_2person["free_cancellation"]
        result["Min 2 Person Price Non-refundable"] = min_price_2person["non_refundable"]
        result["Min 2 Person Price Breakfast Included"] = min_price_2person["breakfast_included"]
    
    # Log the final analysis results
    log_message("Final price analysis:", "info")
    log_message(result, "info", is_scraped_data=True)
    
    return result

def extract_detailed_info(browser: Any, hotel_data: Dict[str, Any], page: Any = None, max_retries: int = 2) -> Dict[str, Any]:
    """
    For a given hotel (with basic info), open the hotel's detail page and extract room-level information.
    Merge the detailed info into the original hotel_data dictionary.

    Args:
        browser (Any): A Playwright browser instance.
        hotel_data (Dict[str, Any]): A dictionary containing basic hotel info, including keys "Hotel Name", 
            "Hotel Link", and optionally "Index" for numbering.
        page (Any, optional): A Playwright page instance to reuse. If None, a new page will be created.
        max_retries (int): Maximum number of retry attempts if extraction fails.

    Returns:
        Dict[str, Any]: The updated hotel_data dictionary with detailed room information added.
    """
    hotel_name: str = hotel_data.get("Hotel Name", "Unknown hotel")
    hotel_index: Any = hotel_data.get("Index", "N/A")
    hotel_link: str = hotel_data.get("Hotel Link", "N/A")
    
    hotel_link_value = hotel_data.pop("Hotel Link", "N/A")
    result = {
        "Min Room Price": "N/A",
        "Min Room Price Free Cancellation": "N/A",
        "Min Room Price Non-refundable": "N/A",
        "Min Room Price Breakfast Included": "N/A",
        "Min 2 Person Price": "N/A",
        "Min 2 Person Price Free Cancellation": "N/A",
        "Min 2 Person Price Non-refundable": "N/A",
        "Min 2 Person Price Breakfast Included": "N/A",
        "Extraction Error": ""
    }
    if not hotel_link_value or hotel_link_value == "N/A":
        log_message(f"No valid hotel link for hotel #{hotel_index}: {hotel_name}, skipping detailed extraction", "warning")
        result["Extraction Error"] = "No valid hotel link"
        hotel_data.update(result)
        hotel_data["Hotel Link"] = hotel_link_value
        return hotel_data

    log_message(f"Starting detail extraction for hotel #{hotel_index}: {hotel_name}", "info")

    # Use the provided page or create one if not given (for backward compatibility)
    if page is None:
        page = browser.new_page()
        close_page_when_done = True
    else:
        close_page_when_done = False

    for retry_attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            # Instead of creating a new page, just navigate to the new hotel URL
            page.set_default_navigation_timeout(40000)
            
            # Using a Promise to implement a timeout for navigation
            navigation_start_time = time.time()
            try:
                log_message(f"Navigating to URL: {hotel_link_value}", "debug")
                page.goto(hotel_link_value, wait_until="domcontentloaded")
                log_message(f"Navigation completed in {time.time() - navigation_start_time:.2f} seconds", "debug")
            except Exception as nav_error:
                log_message(f"Navigation error: {nav_error}", "warning")
                # Check if we need to reload due to timeout
                if time.time() - navigation_start_time > URL_LOADING_REFRESH_TIMEOUT:
                    log_message(f"URL took more than {URL_LOADING_REFRESH_TIMEOUT}s to load, refreshing...", "info")
                    try:
                        page.reload(wait_until="domcontentloaded")
                        log_message("Page refreshed successfully", "debug")
                    except Exception as reload_error:
                        log_message(f"Error refreshing page: {reload_error}", "warning")
            
            # Immediately start scrolling to look for room tables, don't wait for full page load
            try:
                # Scroll down a bit to start loading room tables
                page.evaluate("window.scrollBy(0, 500)")
                time.sleep(0.5)
                page.evaluate("window.scrollBy(0, 500)")
            except Exception as scroll_error:
                log_message(f"Error during initial scroll: {scroll_error}", "debug")
            
            # Check if navigation is taking too long and refresh if needed
            content_found = False
            refresh_needed = False
            
            # Wait for room rows with a more aggressive loading strategy
            selector = f"{ROOM_ROW}, {NO_AVAILABILITY}"
            
            # Initial short wait for content (5s)
            try:
                page.wait_for_selector(selector, timeout=5000)
                content_found = True
                log_message(f"Content found quickly after 5s", "debug")
            except Exception:
                # Content not found immediately, check if page is taking too long
                if time.time() - start_time > URL_LOADING_REFRESH_TIMEOUT:
                    log_message(f"Page taking too long to load (>{URL_LOADING_REFRESH_TIMEOUT}s), refreshing...", "warning")
                    refresh_needed = True
                else:
                    # Try scrolling more to find content
                    try:
                        log_message("Content not found yet, scrolling more...", "debug")
                        page.evaluate("window.scrollBy(0, 700)")
                        time.sleep(0.5)
                        
                        # Try a longer wait after scrolling
                        page.wait_for_selector(selector, timeout=10000)
                        content_found = True
                        log_message("Content found after additional scrolling", "debug")
                    except Exception:
                        # Still no content, time to refresh if it's been too long
                        if time.time() - start_time > URL_LOADING_REFRESH_TIMEOUT:
                            log_message(f"Page still loading slowly after scrolling (>{URL_LOADING_REFRESH_TIMEOUT}s), refreshing...", "warning")
                            refresh_needed = True
            
            # Refresh the page if it's taking too long
            if refresh_needed:
                log_message(f"Refreshing page for hotel {hotel_name} due to slow loading", "warning")
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    
                    # After refresh, try aggressive scrolling to find content
                    for scroll_attempt in range(3):
                        page.evaluate(f"window.scrollBy(0, {500 * (scroll_attempt + 1)})")
                        time.sleep(0.7)
                        
                        # Check if content appears after each scroll
                        if page.query_selector(selector):
                            content_found = True
                            log_message(f"Content found after refresh and scrolling", "debug")
                            break
                    
                    # If still not found, do a final wait
                    if not content_found:
                        page.wait_for_selector(selector, timeout=10000)
                        content_found = True
                except Exception as refresh_err:
                    log_message(f"Error during page refresh: {refresh_err}", "warning")
            
            # Final check if content was found
            if not content_found:
                raise Exception("Content not found after progressive waiting and refresh attempts")
            
            # Check for "no availability" message
            no_availability = page.query_selector(NO_AVAILABILITY)
            if no_availability:
                log_message("No availability message found", "info")
                hotel_data.update(result)
                return hotel_data
            
            # Try to extract using JavaScript for maximum performance
            try:
                rooms = extract_rooms_with_js(page)
                if not rooms:
                    raise Exception("JS extraction returned no rooms")
                
                # Log a summary instead of all room details
                log_message(f"Successfully extracted {len(rooms)} rooms using JavaScript", "info")
                
            except Exception as js_err:
                log_message(f"JS extraction failed: {js_err}, falling back to DOM method", "warning")
                # Fall back to DOM extraction
                room_rows = page.query_selector_all(ROOM_ROW)
                if not room_rows:
                    # Try alternative selector as fallback
                    alt_rows = page.query_selector_all("tr[data-block-id]")
                    room_rows = alt_rows if alt_rows else []
                
                log_message(f"Found {len(room_rows)} room rows using DOM method", "info")
                
                # Extract details for each room
                rooms = []
                for idx, row in enumerate(room_rows):
                    try:
                        room_details = extract_room_details(row, hotel_name, idx)
                        if room_details:
                            rooms.append(room_details)
                    except Exception as e:
                        log_message(f"Error extracting details for room #{idx}: {e}", "warning")
                
                if rooms:
                    log_message(f"Successfully extracted {len(rooms)} rooms using DOM method", "info")
            
            if rooms:
                # Analyze rooms to get min prices
                room_result = analyze_rooms(rooms, hotel_name)
                result.update(room_result)
                result["Extraction Error"] = ""  # Clear any error
                hotel_data.update(result)
                # Add the hotel link at the end
                hotel_data["Hotel Link"] = hotel_link_value
                log_message("Hotel detail extraction completed successfully", "info")
                return hotel_data
            else:
                log_message("No valid room details extracted", "warning")
                result["Extraction Error"] = "No valid room details found"
                if retry_attempt < max_retries:
                    log_message(f"Retrying extraction (attempt {retry_attempt+1}/{max_retries})", "info")
                    continue
                else:
                    hotel_data.update(result)
                    # Add the hotel link at the end
                    hotel_data["Hotel Link"] = hotel_link_value
                    return hotel_data
                
        except Exception as e:
            error_msg = str(e)
            log_message(f"Error during extraction: {error_msg}", "error")
            result["Extraction Error"] = error_msg
            if retry_attempt < max_retries:
                log_message(f"Retrying extraction (attempt {retry_attempt+1}/{max_retries})", "info")
                continue
            else:
                hotel_data.update(result)
                hotel_data["Hotel Link"] = hotel_link_value
                if close_page_when_done:
                    try:
                        page.close()
                    except:
                        pass
                return hotel_data
    
    hotel_data.update(result)
    hotel_data["Hotel Link"] = hotel_link_value
    return hotel_data

def extract_rooms_with_js(page: Any) -> List[Dict[str, Any]]:
    """
    Extract room information using JavaScript for maximum performance.
    
    Args:
        page (Any): A Playwright page object.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing room data.
    """
    extraction_script = """
    () => {
        try {
            // Debug info
            console.log("Starting JS extraction");
            
            const rooms = [];
            // Try multiple selectors for room rows to increase reliability
            let roomRows = document.querySelectorAll('tr.js-rt-block-row');
            
            // If no rows found with primary selector, try alternatives
            if (!roomRows || roomRows.length === 0) {
                console.log("Primary selector found no rooms, trying alternatives");
                roomRows = document.querySelectorAll('tr[data-block-id]');
                
                if (!roomRows || roomRows.length === 0) {
                    roomRows = document.querySelectorAll('div[data-testid="room-item"]');
                }
                
                if (!roomRows || roomRows.length === 0) {
                    // Get all table rows that might contain price information
                    roomRows = Array.from(document.querySelectorAll('tr')).filter(row => {
                        return row.textContent.includes('price') || 
                               row.textContent.includes('€') ||
                               row.textContent.includes('$') ||
                               row.textContent.includes('£') ||
                               row.textContent.includes('¥') ||
                               row.getAttribute('data-hotel-rounded-price');
                    });
                }
                
                if (!roomRows || roomRows.length === 0) {
                    console.log("No room rows found with any selector");
                    return [];
                }
            }
            
            console.log(`Found ${roomRows.length} potential room rows`);
            
            for (let i = 0; i < roomRows.length; i++) {
                const row = roomRows[i];
                try {
                    const roomDetails = {};
                    
                    // Extract price - try multiple approaches
                    let priceStr = row.getAttribute('data-block-price') || 
                                  row.getAttribute('data-hotel-rounded-price') || "";
                    
                    // If no price attribute, try to find price in text content
                    if (!priceStr || priceStr === "") {
                        // Look for price in text content with currency symbols
                        const priceMatch = row.textContent.match(/(?:€|\\$|£|¥|USD|EUR|GBP)\\s*([0-9,.]+)/);
                        if (priceMatch) {
                            priceStr = priceMatch[1].replace(/[^0-9]/g, '');
                        }
                    }
                    
                    // Try to parse the price
                    const price = parseInt(priceStr.trim());
                    if (isNaN(price)) {
                        console.log(`Could not parse price "${priceStr}" for row ${i}`);
                        continue; // Skip this row if price parsing fails
                    }
                    
                    roomDetails.price = price;
                    
                    // Extract max persons - multiple approaches
                    let maxPersons = null;
                    // Try to find explicit max persons label
                    const maxPersonsText = row.querySelector('[data-component="MAX-OCCUPANCY"] .sr-only')?.textContent || 
                                         row.textContent.match(/Max persons:\\s*([0-9]+)/)?.[1] || "";
                    
                    if (maxPersonsText && /[0-9]+/.test(maxPersonsText)) {
                        maxPersons = parseInt(maxPersonsText.match(/[0-9]+/)[0]);
                    } else {
                        // Count person icons
                        const personIcons = row.querySelectorAll('.bui-avatar-block, i.bicon-occupancy');
                        if (personIcons.length > 0) {
                            maxPersons = personIcons.length;
                        } else {
                            // Default to 2 if we can't determine
                            maxPersons = 2;
                        }
                    }
                    roomDetails.max_persons = maxPersons;
                    
                    // Check for free cancellation
                    const policyText = row.textContent || "";
                    roomDetails.free_cancellation = policyText.includes('Free cancellation');
                    roomDetails.non_refundable = policyText.toLowerCase().includes('non-refundable') || 
                                               policyText.toLowerCase().includes('non refundable') ||
                                               policyText.toLowerCase().includes('no refund');
                    
                    // Check for breakfast
                    const hasBreakfast = policyText.toLowerCase().includes('breakfast');
                    roomDetails.has_breakfast_mention = hasBreakfast;
                    
                    // Get breakfast text if mentioned
                    let breakfastText = "";
                    if (hasBreakfast) {
                        // Try to extract the breakfast description
                        const breakfastElement = row.querySelector('[data-component="mealplan-name"]');
                        if (breakfastElement) {
                            breakfastText = breakfastElement.textContent;
                        } else {
                            // Extract the sentence containing "breakfast"
                            const sentences = policyText.split(/[.!?]\\s+/);
                            breakfastText = sentences.find(s => s.toLowerCase().includes('breakfast')) || "";
                        }
                    }
                    roomDetails.breakfast_text = breakfastText.trim();
                    
                    // Determine if breakfast is included
                    roomDetails.breakfast_included = hasBreakfast && 
                        (breakfastText.toLowerCase().includes('included') || 
                         breakfastText.toLowerCase().includes('free breakfast')) &&
                        !breakfastText.toLowerCase().includes('extra') &&
                        !breakfastText.toLowerCase().includes('additional') &&
                        !breakfastText.toLowerCase().includes('surcharge');
                    
                    // Log successful extraction for debugging
                    console.log(`Successfully extracted room ${i+1}: price=${roomDetails.price}, persons=${roomDetails.max_persons}`);
                    
                    rooms.push(roomDetails);
                } catch (e) {
                    console.error(`Error processing room row ${i}:`, e);
                }
            }
            
            console.log(`Completed JS extraction with ${rooms.length} rooms`);
            return rooms;
        } catch (e) {
            console.error("Top-level JS extraction error:", e);
            return [];
        }
    }
    """
    
    # Add debug info to help understand why JS extraction fails
    try:
        # Get page content to analyze in case of failure
        page_title = page.title()
        log_message(f"Extracting rooms from page with title: {page_title}", "debug")
        
        # Execute JS extraction with console logs captured
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        # Execute the script
        rooms = page.evaluate(extraction_script)
        
        # Log console messages at debug level
        for msg in console_messages:
            log_message(f"Browser console: {msg}", "debug")
            
        if not rooms:
            log_message(f"JS extraction found no rooms. Page title: {page_title}", "warning")
            
            # Take a screenshot for debugging if needed
            if not rooms and page_title:
                try:
                    safe_title = "".join(c if c.isalnum() else "_" for c in page_title)
                    screenshot_path = f"debug_{safe_title}_{int(time.time())}.png"
                    page.screenshot(path=screenshot_path)
                    log_message(f"Debug screenshot saved to {screenshot_path}", "debug")
                except Exception as e:
                    log_message(f"Failed to take debug screenshot: {e}", "debug")
        return rooms
    except Exception as e:
        log_message(f"JS extraction error: {e}", "warning")
        # Check if we have console messages that might explain the failure
        if 'console_messages' in locals() and console_messages:
            log_message("Console messages from failed extraction:", "debug")
            for msg in console_messages:
                log_message(f"  {msg}", "debug")
        return []