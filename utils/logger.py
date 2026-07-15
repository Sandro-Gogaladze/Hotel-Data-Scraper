"""
Optimized logging utilities for the Booking.com scraper.

Simplified logging that focuses on showing scraped data in the console
while still keeping detailed logs in files for debugging if needed.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Any

# Ensure the project root is added to sys.path for proper module resolution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import LOG_LEVEL, LOG_DIR

# Create the log directory if it doesn't exist.
os.makedirs(LOG_DIR, exist_ok=True)

# Generate a timestamp for log filenames based on the current date.
timestamp = datetime.now().strftime("%Y-%m-%d")
MAIN_LOG_FILE = os.path.join(LOG_DIR, f"scraper_{timestamp}.log")

def setup_logger() -> logging.Logger:
    """
    Set up a simplified logger focused on showing scraped data.
    - Console: Shows scraped data and essential messages (INFO and above)
    - File: Records all messages for debugging if needed
    """
    # Create a logger with a specified name
    logger = logging.getLogger('booking_scraper')
    logger.setLevel(LOG_LEVEL)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Define formatters
    console_formatter = logging.Formatter('%(message)s')  # Simplified console output
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    
    # Console handler: Shows scraped data and essential messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler: Records all messages for debugging
    file_handler = logging.FileHandler(MAIN_LOG_FILE)
    file_handler.setLevel(logging.DEBUG)  # Still capture debug logs in the file
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

# Create a global logger instance for use throughout the scraper.
logger = setup_logger()

def log_message(message: Any, level: str = 'info', is_scraped_data: bool = False) -> None:
    """
    Log a message at the specified level with special formatting for scraped data.

    Args:
        message (Any): The message to log.
        level (str): The log level ('debug', 'info', 'warning', 'error', 'critical').
        is_scraped_data (bool): Whether this message contains scraped data to highlight.
    """
    level_methods = {
        'debug': logger.debug,
        'info': logger.info,
        'warning': logger.warning,
        'error': logger.error,
        'critical': logger.critical
    }
    # Get the logging method based on level; default to INFO if level not found.
    log_method = level_methods.get(level.lower(), logger.info)
    
    # Format scraped data for better visibility
    if is_scraped_data:
        if isinstance(message, dict):
            # Format dictionary data for better readability
            formatted = "\n" + "-" * 50 + "\nSCRAPED DATA:\n" + "-" * 50
            for key, val in message.items():
                formatted += f"\n{key}: {val}"
            formatted += "\n" + "-" * 50
            log_method(formatted)
        else:
            log_method(f"SCRAPED: {message}")
    else:
        log_method(message)