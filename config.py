"""
Configuration settings for the Booking.com scraper.

This module contains configurable settings for API keys, output directories, logging,
scraping parameters (timeouts, delays, retry counts), GPT API options, and concurrency.
"""

import os
import logging
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from the .env file.
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')

# GPT model parameters.
GPT_MODEL: str = "gpt-4o-mini"
GPT_TEMPERATURE: float = 0.1
GPT_MAX_TOKENS: int = 10

# Output settings
OUTPUT_DIR: str = "Booking_Data"   # Directory in which the output Excel files will be saved.

# Logging configuration
LOG_DIR: str = "logs"               # Directory to store log files.
LOG_LEVEL = logging.INFO            # Use INFO for production, DEBUG for development

# Browser configuration
# Defaults to headed mode for local debugging. Override with the HEADLESS env var
# (e.g. HEADLESS=true) for unattended environments with no display, such as CI.
HEADLESS: bool = os.getenv("HEADLESS", "false").strip().lower() in ("1", "true", "yes")

# Scraping parameters - OPTIMIZED FOR PARALLEL PROCESSING WITH ANTI-DETECTION
LOAD_MORE_TIMEOUT: int = 20000      # Timeout for load more button in milliseconds
SCROLL_DELAY: float = 1.5           # Delay between scrolls in seconds (moderate timing)
LOAD_MORE_DELAY: int = 2            # Delay after clicking load more button in seconds
LOAD_MORE_RETRIES: int = 2          # Extra clicks if "Load more" is still shown but loaded nothing new
SESSION_ATTEMPTS: int = 6           # Fresh sessions to try for the full room table (see scraper/session.py)
HOTEL_WAIT_TIMEOUT: int = 40000     # Timeout for waiting for hotel page elements
INITIAL_LOAD_DELAY: int = 3         # Initial delay after page load in seconds
PAGE_LOAD_TIMEOUT: int = 50000      # Page load timeout in milliseconds
ELEMENT_TIMEOUT: int = 4000         # Default timeout for element operations
RETRY_COUNT: int = 2                # Number of retries for failed operations
RETRY_DELAY: int = 2                # Delay between retries in seconds
INITIAL_NAVIGATION_TIMEOUT: int = 20  # Timeout in seconds for initial hotel page navigation
URL_LOADING_REFRESH_TIMEOUT: int = 12  # Timeout in seconds before refreshing a slow-loading URL

# Concurrency configuration
MAX_WORKERS: int = 6                # Number of parallel processes (aggressive for maximum speed)
                                    # 6 workers for maximum throughput - monitor for rate limiting

# Auto-filling configuration
AUTO_FILLING_ENABLED: bool = True   # Automatically retry hotels with missing price data
MAX_FILLING_RETRIES: int = 2        # Maximum number of retries for missing price data

# Excel styling
EXCEL_HEADER_COLOR: str = "1F4E78"  # Navy blue color for headers
EXCEL_TRUE_COLOR: str = "E2EFDA"    # Light green for TRUE values
EXCEL_FALSE_COLOR: str = "FFDDDD"   # Light red for FALSE values
EXCEL_ERROR_COLOR: str = "FFC7CE"   # Light red for errors