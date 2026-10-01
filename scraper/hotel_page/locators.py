"""
Locators for the Booking.com hotel detail pages.

This module defines a set of constants for CSS selectors and JavaScript code snippets 
used to locate and extract specific elements from hotel detail pages on Booking.com.
"""

# Room selectors
ROOM_ROW = "tr[data-block-id][data-hotel-rounded-price]"
# Selector for a room row element that contains a block ID and a hotel rounded price.

ROOM_PRICE_ATTRIBUTE = "data-hotel-rounded-price"
# Attribute name on a room row which holds the hotel's rounded room price. Note: it's in
# the hotel's own currency, not the displayed one - use DISPLAY_PRICE_JS for the price.

DISPLAY_PRICE_JS = """(row) => {
    const cell = row.querySelector('.hprt-table-cell-price');
    if (!cell) return '';
    const sr = Array.from(cell.querySelectorAll('.bui-u-sr-only'))
        .map(el => el.textContent).join(' ').replace(/\\s+/g, ' ');
    const m = sr.match(/current price\\D*([0-9][0-9,]*(?:\\.[0-9]+)?)/i) ||
              sr.match(/price\\D*([0-9][0-9,]*(?:\\.[0-9]+)?)/i);
    if (m) return m[1];
    const shown = cell.querySelector('.prco-valign-middle-helper');
    const s = shown ? shown.textContent.match(/[0-9][0-9,]*(?:\\.[0-9]+)?/) : null;
    return s ? s[0] : '';
}"""
# JavaScript function (as a string) returning the price a room row displays (the current
# price if discounted), as a numeric string such as "1,322".


# Occupancy selectors
OCCUPANCY_ICON = "i.bicon-occupancy"
# Selector for the icon that represents room occupancy.

SCREEN_READER_TEXT = "span.bui-u-sr-only"
# Selector for the element that contains text meant only for screen readers.


# Availability message
NO_AVAILABILITY = "div:has-text('We have no availability')"
# Selector for an element that indicates there is no availability.


# Room feature JavaScript selectors. These read the *visible* text (innerText) of the row's
# conditions cell: textContent also includes hidden tooltip/modal text that mentions
# "non-refundable" and breakfast prices on rows where neither applies.
FREE_CANCELLATION_JS = """(row) => {
    const text = (row.querySelector('.hprt-table-cell-conditions') || row).innerText || '';
    return /free cancellation/i.test(text) ? 'Free cancellation' : '';
}"""
# JavaScript function (as a string) returning "Free cancellation" if the row's visible
# conditions mention it, else ''.

NON_REFUNDABLE_JS = """(row) => {
    const text = (row.querySelector('.hprt-table-cell-conditions') || row).innerText || '';
    const m = text.match(/non-refundable|non refundable|no refund/i);
    return m ? m[0] : '';
}"""
# JavaScript function (as a string) returning the non-refundable phrase found in the
# row's visible conditions, else ''.

HAS_BREAKFAST_JS = """(row) => {
    const text = (row.querySelector('.hprt-table-cell-conditions') || row).innerText || '';
    return /breakfast|all[- ]inclusive|all meals/i.test(text);
}"""
# JavaScript function (as a string) to determine if the row's visible conditions mention a meal plan.

BREAKFAST_TEXT_JS = """(row) => {
    const text = (row.querySelector('.hprt-table-cell-conditions') || row).innerText || '';
    const line = text.split('\\n').find(l => /breakfast|all[- ]inclusive|all meals/i.test(l));
    return line ? line.replace(/\\s+/g, ' ').trim() : '';
}"""
# JavaScript function (as a string) returning the visible meal-plan line, e.g.
# "Very good breakfast included" or "Very good breakfast GEL 70".

MAX_PERSONS_JS = """(row) => {
    const span = row.querySelector('span.bui-u-sr-only');
    return span ? span.textContent : '';
}"""
# JavaScript function (as a string) to retrieve the text from a span that is intended for screen readers,
# which may indicate the maximum number of persons for the room.