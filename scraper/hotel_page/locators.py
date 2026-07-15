"""
Locators for the Booking.com hotel detail pages.

This module defines a set of constants for CSS selectors and JavaScript code snippets 
used to locate and extract specific elements from hotel detail pages on Booking.com.
"""

# Room selectors
ROOM_ROW = "tr[data-block-id][data-hotel-rounded-price]"
# Selector for a room row element that contains a block ID and a hotel rounded price.

ROOM_PRICE_ATTRIBUTE = "data-hotel-rounded-price"
# Attribute name on a room row which holds the hotel's rounded room price.


# Occupancy selectors
OCCUPANCY_ICON = "i.bicon-occupancy"
# Selector for the icon that represents room occupancy.

SCREEN_READER_TEXT = "span.bui-u-sr-only"
# Selector for the element that contains text meant only for screen readers.


# Availability message
NO_AVAILABILITY = "div:has-text('We have no availability')"
# Selector for an element that indicates there is no availability.


# Room feature JavaScript selectors
FREE_CANCELLATION_JS = """(row) => {
    const elems = row.querySelectorAll('*');
    for (const el of elems) {
        if (el.textContent && el.textContent.includes('Free cancellation')) {
            return el.textContent;
        }
    }
    return '';
}"""
# JavaScript function (as a string) to search through a row's elements for a mention
# of "Free cancellation", returning the corresponding text if found.

NON_REFUNDABLE_JS = """(row) => {
    const elems = row.querySelectorAll('*');
    for (const el of elems) {
        if (el.textContent) {
            const txt = el.textContent.toLowerCase();
            if (txt.includes('non-refundable') || txt.includes('non refundable') || txt.includes('no refund')) {
                return el.textContent;
            }
        }
    }
    return '';
}"""
# JavaScript function (as a string) to check all elements in a row for phrases that indicate
# a non-refundable booking and return the found text.

HAS_BREAKFAST_JS = """(row) => {
    return row.textContent.toLowerCase().includes('breakfast');
}"""
# JavaScript function (as a string) to determine if a row's text mentions 'breakfast'.

BREAKFAST_TEXT_JS = """(row) => {
    const lines = row.textContent.split('\\n');
    return lines.filter(line => line.toLowerCase().includes('breakfast')).join(' ');
}"""
# JavaScript function (as a string) that extracts and joins all lines from a row's text 
# which mention 'breakfast', in order to produce a fuller breakfast description.

MAX_PERSONS_JS = """(row) => {
    const span = row.querySelector('span.bui-u-sr-only');
    return span ? span.textContent : '';
}"""
# JavaScript function (as a string) to retrieve the text from a span that is intended for screen readers,
# which may indicate the maximum number of persons for the room.