"""
Helper functions for the Booking.com scraper.

This module provides functions to safely extract text or attributes from Playwright elements,
evaluate JavaScript on elements, and clean price strings.
"""

import os
import sys
from typing import Any, Optional

# Ensure the project root is in sys.path so that local imports work correctly.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from config import ELEMENT_TIMEOUT

def safe_extract(element: Any, selector: str, attribute: str = "inner_text") -> str:
    """
    Safely extract text or attribute from the first matched element.

    This function uses the provided CSS selector to locate an element and attempts
    to retrieve either its inner text or the specified attribute. If extraction fails,
    it returns "N/A".

    Args:
        element (Any): A Playwright element from which data is to be extracted.
        selector (str): A CSS selector to locate the desired element.
        attribute (str): The type of extraction. Use "inner_text" to obtain text,
                         or specify an attribute name to get that attribute's value.

    Returns:
        str: The extracted text or attribute value, or "N/A" if extraction fails.
    """
    try:
        # Get the first matching element using the provided selector.
        locator = element.locator(selector).first
        # Extract inner text if requested; otherwise, retrieve the attribute.
        if attribute == "inner_text":
            return locator.inner_text(timeout=ELEMENT_TIMEOUT).strip()
        return locator.get_attribute(attribute, timeout=ELEMENT_TIMEOUT).strip()
    except Exception as e:
        log_message(f"Error extracting {attribute} from {selector}: {e}", "debug")
        return "N/A"

def get_element_text(element: Any, javascript_function: str, default: str = "") -> str:
    """
    Get text from an element using JavaScript evaluation.

    This function evaluates the provided JavaScript function on the element to extract
    text information. If the evaluation returns a falsy value or an error occurs, the
    specified default is returned.

    Args:
        element (Any): A Playwright element on which to execute the JavaScript code.
        javascript_function (str): The JavaScript function (as a string) to evaluate.
        default (str): The default value to return if extraction fails. Defaults to an empty string.

    Returns:
        str: The text extracted from the element or the default value if extraction fails.
    """
    try:
        result = element.evaluate(javascript_function)
        return result if result else default
    except Exception as e:
        log_message(f"Error evaluating JavaScript: {e}", "debug")
        return default

def clean_price(price_str: str) -> Optional[int]:
    """
    Clean and convert a price string to an integer.

    This function removes non-numeric characters (except the decimal point) from the
    input string and converts it into an integer. If a decimal point is present, it first
    converts the string to a float and then to an integer.

    Args:
        price_str (str): The price represented as a string (including potential currency symbols,
                         commas, spaces, etc.).

    Returns:
        Optional[int]: The cleaned price as an integer, or None if conversion fails.
    """
    try:
        # Filter out all characters except digits and the decimal point.
        clean_str = ''.join(c for c in price_str if c.isdigit() or c == '.')
        if '.' in clean_str:
            return int(float(clean_str))
        return int(clean_str) if clean_str else None
    except Exception as e:
        log_message(f"Error cleaning price '{price_str}': {e}", "debug")
        return None
