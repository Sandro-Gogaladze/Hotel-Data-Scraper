"""
URL parameter extraction for Booking.com search URLs.

This module provides functionality to extract search parameters from Booking.com URLs,
such as destination, dates, number of guests, and filters.
"""

import re
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import log_message

def extract_booking_params(url: str) -> Dict[str, Any]:
    """
    Extract search parameters from a Booking.com URL.
    
    Args:
        url (str): A Booking.com search URL
        
    Returns:
        Dict[str, Any]: Dictionary containing extracted parameters
    """
    params = {
        "destination": "Unknown",
        "check_in": "Unknown",
        "check_out": "Unknown",
        "adults": "Unknown",
        "children": "Unknown",
        "rooms": "Unknown",
        "filters": []
    }
    
    try:
        # Parse the URL
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Extract destination
        if 'ss' in query_params and query_params['ss']:
            destination = query_params['ss'][0]
            # Clean up URL encoding
            params["destination"] = urllib.parse.unquote(destination)
        
        # Extract dates
        if 'checkin' in query_params and query_params['checkin']:
            params["check_in"] = query_params['checkin'][0]
        
        if 'checkout' in query_params and query_params['checkout']:
            params["check_out"] = query_params['checkout'][0]
            
        # Try alternative date formats
        if params["check_in"] == "Unknown" and 'checkin_year' in query_params:
            try:
                year = query_params.get('checkin_year', [''])[0]
                month = query_params.get('checkin_month', [''])[0]
                day = query_params.get('checkin_monthday', [''])[0]
                if year and month and day:
                    params["check_in"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except Exception:
                pass
                
        if params["check_out"] == "Unknown" and 'checkout_year' in query_params:
            try:
                year = query_params.get('checkout_year', [''])[0]
                month = query_params.get('checkout_month', [''])[0]
                day = query_params.get('checkout_monthday', [''])[0]
                if year and month and day:
                    params["check_out"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except Exception:
                pass
        
        # Extract guests and rooms info
        if 'group_adults' in query_params and query_params['group_adults']:
            params["adults"] = query_params['group_adults'][0]
        
        if 'group_children' in query_params and query_params['group_children']:
            params["children"] = query_params['group_children'][0]
            
        if 'no_rooms' in query_params and query_params['no_rooms']:
            params["rooms"] = query_params['no_rooms'][0]
        
        # Extract filters
        if 'nflt' in query_params and query_params['nflt']:
            filter_string = urllib.parse.unquote(query_params['nflt'][0])
            filters = filter_string.split(';')
            
            for filter_item in filters:
                # Try to make filter items more readable
                if '=' in filter_item:
                    key, value = filter_item.split('=', 1)
                    
                    # Transform known filter codes
                    if key == 'mealplan':
                        if value == '1':
                            params["filters"].append("Breakfast included")
                        elif value == '2':
                            params["filters"].append("Half board")
                        elif value == '3':
                            params["filters"].append("Full board")
                        else:
                            params["filters"].append(f"Meal plan: {value}")
                    elif key == 'ht_id':
                        if value == '204':
                            params["filters"].append("Property type: Hotel")
                        elif value == '201':
                            params["filters"].append("Property type: Apartment")
                        elif value == '203':
                            params["filters"].append("Property type: Guest house")
                        else:
                            params["filters"].append(f"Property type ID: {value}")
                    else:
                        params["filters"].append(f"{key}={value}")
                else:
                    params["filters"].append(filter_item)
        
        # Calculate stay duration if both dates are available
        if params["check_in"] != "Unknown" and params["check_out"] != "Unknown":
            try:
                check_in_date = datetime.strptime(params["check_in"], "%Y-%m-%d")
                check_out_date = datetime.strptime(params["check_out"], "%Y-%m-%d")
                stay_days = (check_out_date - check_in_date).days
                params["duration"] = f"{stay_days} nights"
            except Exception:
                params["duration"] = "Unknown"
        
    except Exception as e:
        log_message(f"Error extracting parameters from URL: {e}", "warning")
    
    return params

def propagate_search_params(search_url: str, hotel_url: str) -> str:
    """
    Copy the search URL's selected_currency and lang onto a hotel URL.

    Hotel links on the search page carry neither, so without this the hotel page falls
    back to the visitor's location: room prices come back in a different currency from
    the search page's, and from a US address booking.com shows no star rating at all
    unless lang is set explicitly (lang=en-gb restores it, the .en-gb path alone doesn't).

    Args:
        search_url (str): The Booking.com search URL
        hotel_url (str): A hotel link scraped from that search page

    Returns:
        str: hotel_url carrying whichever of those parameters the search sets
    """
    search_query = urllib.parse.parse_qs(urllib.parse.urlparse(search_url).query)
    carried = {k: search_query[k] for k in ("selected_currency", "lang") if search_query.get(k)}
    if not carried or not hotel_url or not hotel_url.startswith("http"):
        return hotel_url

    parsed = urllib.parse.urlparse(hotel_url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    for key, value in carried.items():
        query[key] = [value[0]]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))

def get_search_summary(url: str) -> str:
    """
    Generate a human-readable summary of the search parameters.
    
    Args:
        url (str): A Booking.com search URL
        
    Returns:
        str: A formatted summary string
    """
    params = extract_booking_params(url)
    
    summary_parts = []
    
    # Add destination
    if params["destination"] != "Unknown":
        summary_parts.append(f"Destination: {params['destination']}")
    
    # Add dates
    if params["check_in"] != "Unknown" and params["check_out"] != "Unknown":
        summary_parts.append(f"Dates: {params['check_in']} to {params['check_out']}")
        if "duration" in params:
            summary_parts.append(f"Stay: {params['duration']}")
    
    # Add guests
    guests_info = []
    if params["adults"] != "Unknown":
        guests_info.append(f"{params['adults']} adults")
    if params["children"] != "Unknown" and params["children"] != "0":
        guests_info.append(f"{params['children']} children")
    if params["rooms"] != "Unknown":
        guests_info.append(f"{params['rooms']} rooms")
    
    if guests_info:
        summary_parts.append(f"Guests: {', '.join(guests_info)}")
    
    # Add filters
    if params["filters"]:
        summary_parts.append(f"Filters: {', '.join(params['filters'])}")
    
    return " | ".join(summary_parts)
