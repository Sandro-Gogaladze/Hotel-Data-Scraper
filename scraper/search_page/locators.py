"""
Locators for the Booking.com search results page.

This module defines CSS selectors used to locate key elements on the Booking.com 
search results page, including property cards, hotel titles, links, addresses, distances,
prices, reviews, star ratings, and navigation buttons.
"""

# Main selectors
HOTEL_CARD = "div[data-testid='property-card']"
HOTEL_TITLE = "div[data-testid='title']"
HOTEL_LINK = "a[data-testid='title-link']"
HOTEL_ADDRESS = "span[data-testid='address-link'], span[data-testid='address']"
# HOTEL_DISTANCE = "span[data-testid='distance']"
HOTEL_PRICE = "span[data-testid='price-and-discounted-price']"

# Review selectors with multiple approaches to avoid breaking when class names change
# 1. Using data-testid and class-based selectors (may break if classes change)
REVIEW_SCORE = "div[data-testid='review-score'] div.bc946a29db, div[data-testid='review-score'] div.a81870d302"
REVIEW_TEXT = "div[data-testid='review-score'] div.f63b14ab7a.f5463b4b44.becbee2f63, div[data-testid='review-score'] div.becbee2f63, div[data-testid='review-score'] div.f63b14ab7a"
REVIEW_COUNT = "div[data-testid='review-score'] div.eaa845879, div[data-testid='review-score'] div.fff1944c52"

# 2. Structure-based selectors (more resilient to class changes)
STRUCT_REVIEW_SCORE = "div[data-testid='review-score'] > div:first-child"
STRUCT_REVIEW_TEXT = "div[data-testid='review-score'] > div:nth-child(2)"
STRUCT_REVIEW_COUNT = "div[data-testid='review-score'] > div:nth-child(3)"

# 3. Content-based selectors (most resilient but may be slower)
CONTENT_REVIEW_SCORE = "div[data-testid='review-score'] div:first-child"
CONTENT_REVIEW_TEXT = "div[aria-hidden='false'] div:has-text('Excellent'), div[aria-hidden='false'] div:has-text('Very good'), div[aria-hidden='false'] div:has-text('Good'), div[aria-hidden='false'] div:has-text('Fair'), div[aria-hidden='false'] div:has-text('Poor')"
CONTENT_REVIEW_COUNT = "div[data-testid='review-score'] div:has-text('reviews')"

# Full section for content parsing as a last resort
REVIEW_SECTION = "div[data-testid='review-score']"

# Star rating selector
STAR_RATING = "div[aria-label*='out of 5']"

# Navigation selectors
LOAD_MORE_BUTTON = "button:has-text('Load more results')"