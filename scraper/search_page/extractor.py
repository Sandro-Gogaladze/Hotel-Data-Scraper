"""
Functions for extracting data from the Booking.com search results page.

This module contains helper functions that extract a list of hotel card elements
and basic information (such as hotel name, link, address, reviews, and price)
from each hotel card on the search results page.
"""

import os
import sys
import re
import time
from typing import Any, Dict, List

# Ensure that the project root is added to the system path so that local imports work.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from utils.helpers import safe_extract
from .locators import (
    HOTEL_CARD, HOTEL_TITLE, HOTEL_LINK, HOTEL_ADDRESS, 
    HOTEL_PRICE, REVIEW_SCORE, REVIEW_TEXT, REVIEW_COUNT,
    STRUCT_REVIEW_SCORE, STRUCT_REVIEW_TEXT, STRUCT_REVIEW_COUNT,
    CONTENT_REVIEW_SCORE, CONTENT_REVIEW_TEXT, CONTENT_REVIEW_COUNT,
    REVIEW_SECTION, STAR_RATING
)
from config import ELEMENT_TIMEOUT

def normalize_review_score(text: str) -> str:
    """Reduce review score text to the bare number, e.g. "Scored 8.7" -> "8.7".

    The first child of the review-score block is screen-reader text ("Scored 8.7"),
    so the raw selector result includes the word.
    """
    match = re.search(r"\d+(?:\.\d+)?", text or "")
    return match.group(0) if match else "N/A"

def normalize_star_rating(label: str) -> str:
    """Reduce a star aria-label to "N out of 5", e.g.
    "Property rating: 4 out of 5 stars" -> "4 out of 5" (the pre-Sept-2026 format)."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*out of 5", label or "")
    return f"{match.group(1)} out of 5" if match else "N/A"

def get_all_hotel_elements(page: Any) -> List[Any]:
    """
    Retrieve all hotel card elements from the search results page.

    Args:
        page (Any): A Playwright page object representing the loaded search results page.

    Returns:
        List[Any]: A list of hotel card elements.
    """
    # Locate all elements matching the HOTEL_CARD selector.
    hotels = page.locator(HOTEL_CARD).all()
    log_message(f"Found {len(hotels)} hotel cards on search page", "info")
    return hotels

def extract_review_info(hotel_element: Any) -> Dict[str, str]:
    """
    Extract review information using a multi-layered approach for maximum resilience.
    
    This function tries multiple strategies to extract review info:
    1. First with class-based selectors (which may break if classes change)
    2. Then with structure-based selectors (more resilient)
    3. Then with content-based selectors (most resilient)
    4. Finally with JavaScript that parses the entire review section
    
    Args:
        hotel_element (Any): The Playwright element representing a hotel card.
        
    Returns:
        Dict[str, str]: Dictionary with review score, text, and count
    """
    review_info = {
        "Review Score": "N/A",
        "Review Text": "N/A",
        "Number of Reviews": "N/A"
    }
    
    # Step 1: Try class-based selectors first (fastest but least resilient)
    score = safe_extract(hotel_element, REVIEW_SCORE)
    if score != "N/A":
        review_info["Review Score"] = score
    
    text = safe_extract(hotel_element, REVIEW_TEXT)
    if text != "N/A":
        review_info["Review Text"] = text
    
    count = safe_extract(hotel_element, REVIEW_COUNT)
    if count != "N/A":
        review_info["Number of Reviews"] = count
    
    # Step 2: Try structure-based selectors if any values are still missing
    if review_info["Review Score"] == "N/A":
        score = safe_extract(hotel_element, STRUCT_REVIEW_SCORE)
        if score != "N/A":
            review_info["Review Score"] = score
    
    if review_info["Review Text"] == "N/A":
        text = safe_extract(hotel_element, STRUCT_REVIEW_TEXT)
        if text != "N/A":
            review_info["Review Text"] = text
    
    if review_info["Number of Reviews"] == "N/A":
        count = safe_extract(hotel_element, STRUCT_REVIEW_COUNT)
        if count != "N/A":
            review_info["Number of Reviews"] = count
    
    # Step 3: Try content-based selectors as a more resilient approach
    if review_info["Review Score"] == "N/A":
        score = safe_extract(hotel_element, CONTENT_REVIEW_SCORE)
        if score != "N/A":
            review_info["Review Score"] = score
    
    if review_info["Review Text"] == "N/A":
        text = safe_extract(hotel_element, CONTENT_REVIEW_TEXT)
        if text != "N/A":
            review_info["Review Text"] = text
    
    if review_info["Number of Reviews"] == "N/A":
        count = safe_extract(hotel_element, CONTENT_REVIEW_COUNT)
        if count != "N/A":
            review_info["Number of Reviews"] = count

    if review_info["Review Score"] != "N/A":
        review_info["Review Score"] = normalize_review_score(review_info["Review Score"])

    # Step 4: Most robust approach - try JavaScript extraction specifically for review text
    if review_info["Review Text"] == "N/A" or review_info["Review Text"] == review_info["Review Score"]:
        try:
            js_result = hotel_element.evaluate("""
                element => {
                    // Look for elements with review text quality descriptions
                    const reviewSection = element.querySelector('div[data-testid="review-score"]');
                    if (!reviewSection) return null;
                    
                    // First try the aria-hidden="false" element which often contains the text
                    const visibleDiv = reviewSection.querySelector('div[aria-hidden="false"]');
                    if (visibleDiv) {
                        const textContent = visibleDiv.textContent.trim();
                        const qualityTexts = ['Excellent', 'Very good', 'Good', 'Fair', 'Poor'];
                        for (const quality of qualityTexts) {
                            if (textContent.includes(quality)) {
                                return quality;
                            }
                        }
                    }
                    
                    // If not found, look for specific class names that might contain the text
                    const reviewTextElements = reviewSection.querySelectorAll('.f63b14ab7a, .becbee2f63, .f5463b4b44');
                    for (const el of reviewTextElements) {
                        const text = el.textContent.trim();
                        if (['Excellent', 'Very good', 'Good', 'Fair', 'Poor'].includes(text)) {
                            return text;
                        }
                    }
                    
                    // Last resort: check all divs in the review section
                    const allDivs = reviewSection.querySelectorAll('div');
                    const qualityTexts = ['Excellent', 'Very good', 'Good', 'Fair', 'Poor'];
                    for (const div of allDivs) {
                        const content = div.textContent.trim();
                        for (const quality of qualityTexts) {
                            if (content === quality) {
                                return quality;
                            }
                        }
                    }
                    
                    return null;
                }
            """)
            
            if js_result:
                review_info["Review Text"] = js_result
        except Exception as e:
            log_message(f"JavaScript extraction for review text failed: {e}", "debug")
    
    # Make sure review text is not the same as review score (indicating an extraction error)
    if review_info["Review Text"] == review_info["Review Score"]:
        # Try one more approach with a score-to-text mapping
        try:
            score_float = float(review_info["Review Score"])
            if score_float >= 9.0:
                review_info["Review Text"] = "Excellent"
            elif score_float >= 8.0:
                review_info["Review Text"] = "Very good"
            elif score_float >= 7.0:
                review_info["Review Text"] = "Good"
            elif score_float >= 6.0:
                review_info["Review Text"] = "Fair"
            else:
                review_info["Review Text"] = "Poor"
            log_message(f"Applied score-to-text mapping: {score_float} → {review_info['Review Text']}", "debug")
        except Exception:
            review_info["Review Text"] = "N/A"  # Reset to N/A if we can't determine text
    
    # If we still have nothing, try one last approach: extract the entire section text
    if review_info["Review Score"] == "N/A" or review_info["Review Text"] == "N/A" or review_info["Number of Reviews"] == "N/A":
        try:
            section_text = safe_extract(hotel_element, REVIEW_SECTION)
            if section_text != "N/A":
                # Extract score with regex
                if review_info["Review Score"] == "N/A":
                    score_match = re.search(r'([0-9]\.[0-9]|10\.0|[0-9])', section_text)
                    if score_match:
                        review_info["Review Score"] = score_match.group(1)
                
                # Extract review quality text
                if review_info["Review Text"] == "N/A":
                    text_match = re.search(r'(Excellent|Very good|Good|Fair|Poor)', section_text)
                    if text_match:
                        review_info["Review Text"] = text_match.group(1)
                
                # Extract review count
                if review_info["Number of Reviews"] == "N/A":
                    count_match = re.search(r'([0-9,]+)\s+reviews?', section_text, re.IGNORECASE)
                    if count_match:
                        review_info["Number of Reviews"] = count_match.group(0)
        except Exception as e:
            log_message(f"Regex extraction from section text failed: {e}", "debug")
    
    return review_info

def extract_hotel_basic_info(hotel_element: Any, index: int) -> Dict[str, Any]:
    """
    Extract basic hotel information from a single hotel card.

    Retrieves information such as hotel name, link, address, distance,
    review score and text, review count, price, and star rating.

    Args:
        hotel_element (Any): The Playwright element representing a hotel card.
        index (int): The sequential index of the hotel (used for logging).

    Returns:
        Dict[str, Any]: A dictionary with the extracted basic hotel information.
    """
    log_message(f"Extracting basic info for hotel #{index + 1}", "debug")
    
    # Build a dictionary of hotel data by using the safe_extract helper to retrieve text or attributes.
    hotel_data: Dict[str, Any] = {
        "Hotel Name": safe_extract(hotel_element, HOTEL_TITLE),
        "Hotel Link": safe_extract(hotel_element, HOTEL_LINK, attribute="href"),
        "Address": safe_extract(hotel_element, HOTEL_ADDRESS),
        # "Distance": safe_extract(hotel_element, HOTEL_DISTANCE),
        "Price": safe_extract(hotel_element, HOTEL_PRICE),
    }
    
    # Extract review information using the dedicated function
    review_info = extract_review_info(hotel_element)
    hotel_data.update(review_info)
    
    # --- Extract the star rating ---
    try:
        # Locate the first element matching the STAR_RATING selector.
        star_element = hotel_element.locator(STAR_RATING).first
        # Retrieve the "aria-label" attribute which contains the star rating.
        stars_attr = star_element.get_attribute("aria-label", timeout=ELEMENT_TIMEOUT)
        hotel_data["Stars"] = normalize_star_rating(stars_attr)
    except Exception as e:
        log_message(f"Error extracting stars for hotel {hotel_data.get('Hotel Name', 'Unknown')}", "debug")
        hotel_data["Stars"] = "N/A"
    
    # Log the scraped data with improved formatting
    log_message(hotel_data, "info", is_scraped_data=True)
    
    return hotel_data

def batch_extract_basic_info(page: Any) -> List[Dict[str, Any]]:
    """
    Extract basic information from all hotels on the page using JavaScript for performance.
    This function executes a single JavaScript call that processes all hotels at once,
    which is much faster than processing each hotel individually.
    
    Args:
        page (Any): A Playwright page object representing the loaded search results page.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries with basic hotel information.
    """
    log_message("Starting batch extraction using JavaScript", "info")
    start_time = time.time()
    
    # Define a JavaScript function that will extract all data in one pass
    # using locators from the locators.py file
    extraction_script = """
    () => {
        const hotels = [];
        const hotelCards = document.querySelectorAll('div[data-testid="property-card"]');
        
        for (const card of hotelCards) {
            try {
                const hotelData = {};
                
                // Extract hotel name
                const titleElement = card.querySelector('div[data-testid="title"]');
                hotelData["Hotel Name"] = titleElement ? titleElement.innerText.trim() : "N/A";
                
                // Extract hotel link
                const linkElement = card.querySelector('a[data-testid="title-link"]');
                hotelData["Hotel Link"] = linkElement ? linkElement.href : "N/A";
                
                // Extract address
                const addressElement = card.querySelector('span[data-testid="address-link"]')
                                    || card.querySelector('span[data-testid="address"]');
                hotelData["Address"] = addressElement ? addressElement.innerText.trim() : "N/A";
                
                // Extract price
                const priceElement = card.querySelector('span[data-testid="price-and-discounted-price"]');
                hotelData["Price"] = priceElement ? priceElement.innerText.trim() : "N/A";
                
                // Extract review score using a robust approach
                let scoreEl = null;
                // First try class-based approach
                scoreEl = card.querySelector('div[data-testid="review-score"] .bc946a29db, div[data-testid="review-score"] .a81870d302');
                
                // If that fails, try structure-based approach
                if (!scoreEl) {
                    scoreEl = card.querySelector('div[data-testid="review-score"] > div:first-child');
                }
                
                // If still nothing, try content-based pattern matching
                if (!scoreEl || !scoreEl.innerText.trim()) {
                    const reviewSection = card.querySelector('div[data-testid="review-score"]');
                    if (reviewSection) {
                        const divs = reviewSection.querySelectorAll('div');
                        for (const div of divs) {
                            const text = div.innerText.trim();
                            // Look for number pattern like score
                            if (/^[0-9]\\.?[0-9]?$/.test(text) || /^10\\.?0?$/.test(text)) {
                                scoreEl = div;
                                break;
                            }
                        }
                    }
                }
                
                // The first child is screen-reader text ("Scored 8.7"), so keep only the number.
                const scoreNum = scoreEl && scoreEl.innerText ? scoreEl.innerText.match(/\\d+(?:\\.\\d+)?/) : null;
                hotelData["Review Score"] = scoreNum ? scoreNum[0] : "N/A";
                
                // Similar robust approach for review text (Excellent, Very good, etc.)
                let textEl = null;
                // First try class-based approach with more specific classes
                textEl = card.querySelector('div[aria-hidden="false"] div.becbee2f63, div[aria-hidden="false"] div.f63b14ab7a, div[aria-hidden="false"] div.f5463b4b44');
                
                // If that fails, try to find element with specific text values
                if (!textEl || !textEl.innerText.trim()) {
                    const qualityTexts = ['Excellent', 'Very good', 'Good', 'Fair', 'Poor'];
                    const reviewSection = card.querySelector('div[data-testid="review-score"]');
                    
                    if (reviewSection) {
                        // First check visible elements
                        const visibleDiv = reviewSection.querySelector('div[aria-hidden="false"]');
                        if (visibleDiv) {
                            for (const quality of qualityTexts) {
                                if (visibleDiv.innerText.includes(quality)) {
                                    textEl = visibleDiv;
                                    break;
                                }
                            }
                        }
                        
                        // If still not found, check all divs for exact quality text match
                        if (!textEl) {
                            const allDivs = reviewSection.querySelectorAll('div');
                            for (const div of allDivs) {
                                const text = div.innerText.trim();
                                if (qualityTexts.includes(text)) {
                                    textEl = div;
                                    break;
                                }
                            }
                        }
                    }
                }
                
                // Extract the text if element was found
                let reviewText = textEl && textEl.innerText ? textEl.innerText.trim() : "N/A";
                
                // Make sure review text is not the same as the score (which would be an error)
                if (reviewText === hotelData["Review Score"] || reviewText === "N/A") {
                    // Try to map score to quality text
                    const score = parseFloat(hotelData["Review Score"]);
                    if (!isNaN(score)) {
                        if (score >= 9.0) reviewText = "Excellent";
                        else if (score >= 8.0) reviewText = "Very good";
                        else if (score >= 7.0) reviewText = "Good";
                        else if (score >= 6.0) reviewText = "Fair";
                        else reviewText = "Poor";
                    }
                }
                
                hotelData["Review Text"] = reviewText;
                
                // Similar robust approach for review count
                let countEl = null;
                // First try class-based approach
                countEl = card.querySelector('div[data-testid="review-score"] .eaa845879, div[data-testid="review-score"] .fff1944c52');
                
                // If that fails, try structure-based approach
                if (!countEl) {
                    countEl = card.querySelector('div[data-testid="review-score"] > div:nth-child(3)');
                }
                
                // If still nothing, try content-based pattern matching
                if (!countEl || !countEl.innerText.trim()) {
                    const reviewSection = card.querySelector('div[data-testid="review-score"]');
                    if (reviewSection) {
                        const divs = reviewSection.querySelectorAll('div');
                        for (const div of divs) {
                            const text = div.innerText.trim();
                            if (text.includes('review')) {
                                countEl = div;
                                break;
                            }
                        }
                    }
                }
                
                hotelData["Number of Reviews"] = countEl && countEl.innerText ? countEl.innerText.trim() : "N/A";
                
                // If all else fails, try to extract from the full review section text
                if (hotelData["Review Score"] === "N/A" || hotelData["Review Text"] === "N/A" || hotelData["Number of Reviews"] === "N/A") {
                    const reviewSection = card.querySelector('div[data-testid="review-score"]');
                    if (reviewSection) {
                        const fullText = reviewSection.innerText;
                        
                        // Try to extract score with regex
                        if (hotelData["Review Score"] === "N/A") {
                            const scoreMatch = fullText.match(/([0-9]\\.[0-9]|10\\.0|[0-9])/);
                            if (scoreMatch) {
                                hotelData["Review Score"] = scoreMatch[0];
                            }
                        }
                        
                        // Try to extract review text
                        if (hotelData["Review Text"] === "N/A") {
                            const qualityTexts = ['Excellent', 'Very good', 'Good', 'Fair', 'Poor'];
                            for (const quality of qualityTexts) {
                                if (fullText.includes(quality)) {
                                    hotelData["Review Text"] = quality;
                                    break;
                                }
                            }
                        }
                        
                        // Try to extract review count
                        if (hotelData["Number of Reviews"] === "N/A") {
                            const countMatch = fullText.match(/([0-9,]+)\\s+reviews?/i);
                            if (countMatch) {
                                hotelData["Number of Reviews"] = countMatch[0];
                            }
                        }
                    }
                }
                
                // Extract star rating. The label lives on a <button> since Sept 2026
                // ("Property rating: 4 out of 5 stars"); normalize to "4 out of 5".
                const starElement = card.querySelector('[aria-label*="out of 5"]');
                const starMatch = starElement ? starElement.getAttribute("aria-label").match(/(\\d+(?:\\.\\d+)?)\\s*out of 5/) : null;
                hotelData["Stars"] = starMatch ? `${starMatch[1]} out of 5` : "N/A";
                
                // Add index for tracking
                hotelData["Index"] = hotels.length + 1;
                
                hotels.push(hotelData);
            } catch (e) {
                console.error("Error processing hotel card:", e);
            }
        }
        
        return hotels;
    }
    """
    
    try:
        # Execute the JavaScript and get the results
        hotels_data = page.evaluate(extraction_script)
        extraction_time = time.time() - start_time
        
        # Log the results
        log_message(f"✅ Batch extraction completed: {len(hotels_data)} hotels in {extraction_time:.2f} seconds", "info")
        log_message(f"Average time per hotel: {extraction_time/max(1, len(hotels_data)):.4f} seconds", "info")
        
        # Log a sample of what was extracted
        if hotels_data:
            log_message("Sample of extracted data:", "info")
            sample_hotel = hotels_data[0]
            log_message(sample_hotel, "info", is_scraped_data=True)
            
        return hotels_data
    except Exception as e:
        log_message(f"❌ Error during batch extraction: {e}", "error")
        # Fall back to standard extraction if batch extraction fails
        log_message("Falling back to standard extraction", "warning")
        hotel_elements = get_all_hotel_elements(page)
        return [extract_hotel_basic_info(hotel, idx) for idx, hotel in enumerate(hotel_elements)]