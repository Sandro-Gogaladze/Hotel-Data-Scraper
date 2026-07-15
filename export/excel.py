"""
Excel export functionality for Booking.com scraper.

This module provides functions to save scraped hotel data to an Excel file with formatting
such as color-coding for TRUE/FALSE values, clickable links, and better styling for headers.
"""

import os
import sys
import pandas as pd
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.cell.cell import Cell
from datetime import datetime

# Ensure the project root is in sys.path for proper module resolution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import log_message
from utils.url_parser import extract_booking_params, get_search_summary
from config import EXCEL_HEADER_COLOR, EXCEL_TRUE_COLOR, EXCEL_FALSE_COLOR, EXCEL_ERROR_COLOR

def save_to_excel(data: List[Dict[str, Any]], output_file: str, search_url: str = None, duration_seconds: float = None) -> None:
    """
    Save the collected hotel data to an Excel file with formatting.

    This function converts a list of hotel data dictionaries into a pandas DataFrame,
    creates an Excel file with formatting like color-coded TRUE/FALSE values,
    styled headers, and adjusted column widths. It also makes hotel links clickable
    and includes the search parameters if a URL is provided.

    Args:
        data (List[Dict[str, Any]]): A list of dictionaries representing hotel data.
        output_file (str): The path (including filename) where the Excel file will be saved.
        search_url (str, optional): The original Booking.com search URL to extract parameters from.
        duration_seconds (float, optional): The duration of the script run in seconds.
    """
    log_message(f"Preparing to save data to Excel: {output_file}", "debug")
    
    if not data:
        log_message("No data to save!", "error")
        return
    
    try:
        # Convert the list of dictionaries into a pandas DataFrame.
        df = pd.DataFrame(data)
        log_message(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns", "debug")

        # Insert 'Execution Error' column before 'Hotel Link'
        if "Hotel Link" in df.columns:
            link_idx = df.columns.get_loc("Hotel Link")
            # Compute Execution Error: True if Extraction Error is present and not empty, else ""
            exec_error_col = []
            for i, row in df.iterrows():
                val = row.get("Extraction Error", "")
                exec_error_col.append(True if val and str(val).strip() else "")
            df.insert(link_idx, "Execution Error", exec_error_col)
        else:
            # If Hotel Link not present, just add at the end
            exec_error_col = []
            for i, row in df.iterrows():
                val = row.get("Extraction Error", "")
                exec_error_col.append(True if val and str(val).strip() else "")
            df["Execution Error"] = exec_error_col

        # Drop unwanted columns if present (but keep Extraction Error for logic above)
        for col in ["Distance", "Index", "Extraction Error"]:
            if col in df.columns:
                df.drop(col, axis=1, inplace=True)
                log_message(f"Dropped '{col}' column from DataFrame", "debug")
        
        # Create a new Excel workbook and select the active worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Hotel Data"
        
        # If we have a search URL, extract and add search parameters to the worksheet
        if search_url:
            add_search_parameters(wb, search_url, duration_seconds)
        
        # Add rows from dataframe to worksheet
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                
                # Format header row
                if r_idx == 1:
                    format_header_cell(cell)
                
                # Format TRUE/FALSE values
                elif isinstance(value, bool):
                    format_boolean_cell(cell, value)
                
                # Format errors
                elif value == "N/A":
                    cell.fill = PatternFill(start_color=EXCEL_ERROR_COLOR, end_color=EXCEL_ERROR_COLOR, fill_type="solid")
                
                # Format Hotel Link column with hyperlinks
                if r_idx > 1 and df.columns[c_idx-1] == 'Hotel Link' and isinstance(value, str) and value.startswith('http'):
                    # Create a hyperlink that is clickable
                    make_cell_hyperlink(cell, value)
        
        # Auto-adjust column widths, with special handling for the Hotel Link column
        auto_adjust_column_widths(ws, df.columns)
        
        # Save the workbook
        wb.save(output_file)
        log_message(f"✅ Excel file successfully created: {output_file}", "info")
        
        # Log summary information
        log_extraction_statistics(data)
        
    except Exception as e:
        # Log any error encountered while saving the Excel file.
        log_message(f"Error saving data to Excel: {e}", "error")
        
        # Try to save as CSV as a fallback
        try:
            csv_output = output_file.replace('.xlsx', '.csv')
            df.to_csv(csv_output, index=False)
            log_message(f"Saved data as CSV instead: {csv_output}", "warning")
        except Exception as csv_err:
            log_message(f"Also failed to save as CSV: {csv_err}", "error")

def add_search_parameters(workbook: Workbook, search_url: str, duration_seconds: float = None) -> None:
    """
    Add a worksheet with search parameters extracted from the Booking.com URL.
    
    Args:
        workbook (Workbook): The Excel workbook object
        search_url (str): The Booking.com search URL
        duration_seconds (float, optional): The duration of the script run in seconds.
    """
    # Create a new worksheet for search parameters
    ws = workbook.create_sheet(title="Search Parameters")
    
    # Extract parameters from URL
    params = extract_booking_params(search_url)
    
    # Add a title
    ws.append(["Booking.com Search Parameters"])
    ws.merge_cells(f"A1:B1")
    title_cell = ws.cell(row=1, column=1)
    title_cell.font = Font(size=14, bold=True)
    title_cell.alignment = Alignment(horizontal='center')
    
    # Add today's date - changed "Export Date" to "Data Collection Date"
    today_str = datetime.today().strftime("%Y-%m-%d")
    ws.append(["Data Collection Date", today_str])

    # Add run duration if provided
    if duration_seconds is not None:
        mins, secs = divmod(int(duration_seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            duration_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            duration_str = f"{mins}m {secs}s"
        else:
            duration_str = f"{secs}s"
        ws.append(["Script Run Duration", duration_str])
    
    # Add search URL with special formatting for long URLs
    ws.append(["Search URL", search_url])
    url_cell = ws.cell(row=ws.max_row, column=2)
    url_cell.hyperlink = search_url
    url_cell.font = Font(color="0000FF", underline="single")
    url_cell.alignment = Alignment(wrap_text=True, vertical='top')  # Enable text wrapping
    
    # Add parameters
    ws.append(["Destination", params["destination"]])
    ws.append(["Check-in Date", params["check_in"]])
    ws.append(["Check-out Date", params["check_out"]])
    
    # Add duration if available
    if "duration" in params:
        ws.append(["Stay Duration", params["duration"]])
    else:
        # Try to calculate duration if not present
        try:
            check_in = params.get("check_in")
            check_out = params.get("check_out")
            if check_in != "Unknown" and check_out != "Unknown":
                d1 = datetime.strptime(check_in, "%Y-%m-%d")
                d2 = datetime.strptime(check_out, "%Y-%m-%d")
                duration = (d2 - d1).days
                ws.append(["Stay Duration", f"{duration} nights"])
        except Exception:
            ws.append(["Stay Duration", "Unknown"])
        
    ws.append(["Adults", params["adults"]])
    ws.append(["Children", params["children"]])
    ws.append(["Rooms", params["rooms"]])
    
    # Add filters
    if params["filters"]:
        ws.append(["Filters", ""])
        for i, filter_item in enumerate(params["filters"]):
            ws.append(["", filter_item])
    
    # Format parameter cells
    for row in range(2, ws.max_row + 1):
        param_name_cell = ws.cell(row=row, column=1)
        param_name_cell.font = Font(bold=True)
        
        # Add a border to all cells
        for col in range(1, 3):
            cell = ws.cell(row=row, column=col)
            cell.border = Border(
                left=Side(style='thin'), 
                right=Side(style='thin'), 
                top=Side(style='thin'), 
                bottom=Side(style='thin')
            )
    
    # Adjust column widths - make wider to accommodate long content
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 120  # Increased from 80 to 120
    
    # Adjust row heights for URL row (row 4 if there's duration info, row 3 if not)
    url_row = 4 if duration_seconds is not None else 3
    ws.row_dimensions[url_row].height = 60  # Make URL row taller
    
    # Remove the search summary section entirely
    
    # Make the Parameters worksheet the active one when opening
    workbook.active = workbook["Hotel Data"]

def format_header_cell(cell: Cell) -> None:
    """Format a header cell with style and background color."""
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill(start_color=EXCEL_HEADER_COLOR, end_color=EXCEL_HEADER_COLOR, fill_type="solid")
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Add a border to the header cell
    cell.border = Border(
        left=Side(style='thin'), 
        right=Side(style='thin'), 
        top=Side(style='thin'), 
        bottom=Side(style='thin')
    )

def format_boolean_cell(cell: Cell, value: bool) -> None:
    """Format a boolean cell based on its value."""
    if value:  # True value
        cell.fill = PatternFill(start_color=EXCEL_TRUE_COLOR, end_color=EXCEL_TRUE_COLOR, fill_type="solid")
    else:  # False value
        cell.fill = PatternFill(start_color=EXCEL_FALSE_COLOR, end_color=EXCEL_FALSE_COLOR, fill_type="solid")

def make_cell_hyperlink(cell: Cell, url: str) -> None:
    """Make a cell a clickable hyperlink using the URL as both link and display text."""
    # Use the URL as the cell's value and add a hyperlink
    cell.hyperlink = url
    
    # Format the cell as a hyperlink with blue, underlined text
    cell.font = Font(color="0000FF", underline="single")
    
    # Create a shorter display text (keep domain and part of the path)
    # For example: "https://www.booking.com/hotel/ge/rooms-kokhta.en-gb.html?..." -> "booking.com/hotel/ge/rooms-kokhta..."
    try:
        if url.startswith('http'):
            parts = url.split('/')
            if len(parts) >= 3:
                # Extract domain without "www." if present
                domain = parts[2]
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                # Get part of the path
                path = '/'.join(parts[3:5])  # Take the next two path components
                if len(parts) > 5:
                    path += '/...'  # Add ellipsis if there are more components
                
                # Set the display value
                display_text = f"{domain}/{path}"
                cell.value = display_text
    except:
        # If anything goes wrong, keep the full URL
        pass
    
    # Set alignment and wrap text
    cell.alignment = Alignment(vertical='top', wrap_text=True)

def auto_adjust_column_widths(ws: Worksheet, columns: List[str]) -> None:
    """Automatically adjust column widths based on content."""
    for idx, column_name in enumerate(columns, 1):
        max_length = len(str(column_name)) + 2  # Start with the header length
        
        # Set column letter
        column_letter = ws.cell(row=1, column=idx).column_letter
        
        # Check all cells in the column
        for row in range(2, ws.max_row + 1):
            cell_value = ws.cell(row=row, column=idx).value
            if cell_value:
                cell_length = len(str(cell_value))
                if column_name == "Hotel Link":
                    # For URLs, use a fixed width
                    max_length = 40
                    break
                else:
                    max_length = max(max_length, min(cell_length, 100))
        
        # Set the column width (with limits to prevent too wide columns)
        ws.column_dimensions[column_letter].width = min(max_length, 60)
        
        # Special formatting for specific columns
        if column_name == "Hotel Name":
            ws.column_dimensions[column_letter].width = min(40, max_length)
        
        # Set wrap text for all columns that might contain long text
        if column_name in ["Hotel Name", "Address", "Hotel Link", "Review Text"]:
            for row in range(1, ws.max_row + 1):
                ws.cell(row=row, column=idx).alignment = Alignment(wrap_text=True)

def log_extraction_statistics(data: List[Dict[str, Any]]) -> None:
    """Log statistics about the extracted data."""
    log_message(f"Total hotels scraped: {len(data)}", "info")
    
    # Count hotels with extraction failures
    extraction_failures = sum(1 for hotel in data if hotel.get("Extraction Error", ""))
    if extraction_failures > 0:
        log_message(f"Hotels with extraction failures: {extraction_failures}/{len(data)}", "warning")
    
    # Count hotels with available rooms (Min Room Price not marked as "N/A")
    available_rooms = sum(1 for hotel in data if hotel.get("Min Room Price") != "N/A")
    log_message(f"Hotels with available rooms: {available_rooms}/{len(data)}", "info")
    
    # Count hotels with breakfast included
    breakfast_included = sum(1 for hotel in data if hotel.get("Min Room Price Breakfast Included") is True)
    log_message(f"Hotels with breakfast included: {breakfast_included}/{len(data)}", "info")
    
    # Count hotels with free cancellation
    free_cancellation = sum(1 for hotel in data if hotel.get("Min Room Price Free Cancellation") is True)
    log_message(f"Hotels with free cancellation: {free_cancellation}/{len(data)}", "info")
