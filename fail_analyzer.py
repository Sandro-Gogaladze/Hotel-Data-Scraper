#!/usr/bin/env python3
"""
Extraction Failure Analyzer for Booking.com Scraper.

This module analyzes the most recent scraping session in the log file to identify
hotels where data extraction failed, then uses GPT to analyze these failures
and provide recommendations for improvement.
"""

import os
import sys
import re
from datetime import datetime
import openai
from typing import Optional, Tuple, List, Dict, Any

# Get the project root directory.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import project configurations.
from config import LOG_DIR, OPENAI_API_KEY

# Set up OpenAI API.
openai.api_key = OPENAI_API_KEY

def get_latest_logs() -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieve the path to the latest scraper log file.

    Since the scraper log (named "scraper_YYYY-MM-DD.log") contains all levels of logs,
    we use it for analysis rather than separate error logs.

    Returns:
        Tuple[Optional[str], Optional[str]]: Both elements are the path to the latest scraper log file,
        or (None, None) if no log file is found.
    """
    if not os.path.exists(LOG_DIR):
        print(f"Error: Log directory '{LOG_DIR}' not found.")
        return None, None

    # Construct the expected log file name for today.
    today: str = datetime.now().strftime("%Y-%m-%d")
    main_log: str = os.path.join(LOG_DIR, f"scraper_{today}.log")
    
    # If today's scraper log doesn't exist, search for the most recent one.
    if not os.path.exists(main_log):
        all_files: List[str] = os.listdir(LOG_DIR)
        log_pattern = re.compile(r"^scraper_(\d{4}-\d{2}-\d{2})\.log$")
        
        latest_date: Optional[str] = None
        for filename in all_files:
            match = log_pattern.match(filename)
            if match:
                date_str: str = match.group(1)
                if latest_date is None or date_str > latest_date:
                    latest_date = date_str
        
        if latest_date:
            main_log = os.path.join(LOG_DIR, f"scraper_{latest_date}.log")
        else:
            main_log = None

    # Return the main_log twice so that both parameters use the same file.
    return main_log, main_log

def extract_most_recent_session(log_path: str) -> List[str]:
    """
    Extract log lines for the most recent scraping session.
    
    A new session is identified by the log message "🚀 Starting Booking.com scraper..."
    
    Args:
        log_path (str): Path to the log file
        
    Returns:
        List[str]: Log lines for the most recent session
    """
    if not log_path or not os.path.exists(log_path):
        return []
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            
        # Split the file by the session start marker
        session_marker = "🚀 Starting Booking.com scraper..."
        sessions = content.split(session_marker)
        
        # If there's only one element, there are no sessions or just one partial session
        if len(sessions) <= 1:
            return content.splitlines()
        
        # Get the most recent session (last split part) and add the marker back
        most_recent = session_marker + sessions[-1]
        return most_recent.splitlines()
    
    except Exception as e:
        print(f"Error extracting most recent session: {e}")
        return []

def find_extraction_failures(error_log_path: Optional[str], main_log_path: Optional[str]) -> List[Dict[str, str]]:
    """
    Analyze the most recent session in the provided log file to identify hotels with extraction failures.
    The analysis focuses on indicators such as missing room data, timeouts, no availability,
    and other logged errors.

    Args:
        error_log_path (Optional[str]): Path to the error log file (unused in this version).
        main_log_path (Optional[str]): Path to the main scraper log file.

    Returns:
        List[Dict[str, str]]: A list of dictionaries with keys 'hotel_name' and 'failure_reason'.
    """
    failures: List[Dict[str, str]] = []
    hotel_errors: Dict[str, Dict[str, Any]] = {}
    
    if not main_log_path or not os.path.exists(main_log_path):
        return failures
    
    # Extract only the most recent session from the log file
    log_lines = extract_most_recent_session(main_log_path)
    if not log_lines:
        print("No recent session found in logs.")
        return failures
    
    print(f"Analyzing most recent session with {len(log_lines)} log lines")
    
    # Define regex patterns to capture different failure scenarios
    hotel_processing_pattern = re.compile(r"Starting detail extraction for hotel #\d+: (.+)")
    hotel_completion_pattern = re.compile(r"Completed detail extraction for hotel #\d+: (.+)")
    no_data_pattern = re.compile(r"No rooms found for (.+)")
    timeout_pattern = re.compile(r"Timed out waiting for room rows.*for (.+)")
    no_availability_pattern = re.compile(r"No availability message found for (.+)")
    js_extraction_failed_pattern = re.compile(r"JS extraction failed: (.*), falling back to DOM method")
    hotel_data_success_pattern = re.compile(r"Successfully extracted details for (\d+) rooms at (.+)")
    navigation_error_pattern = re.compile(r"Error loading URL.*: (.*)")
    
    # Process the log lines to identify hotels being processed and their status
    for line in log_lines:
        # Check if a hotel is being processed
        hotel_processing_match = hotel_processing_pattern.search(line)
        if hotel_processing_match:
            hotel_name = hotel_processing_match.group(1)
            if hotel_name not in hotel_errors:
                hotel_errors[hotel_name] = {"status": "processing", "errors": []}
        
        # Check if a hotel was completed successfully
        hotel_completion_match = hotel_completion_pattern.search(line)
        if hotel_completion_match:
            hotel_name = hotel_completion_match.group(1)
            if hotel_name in hotel_errors:
                hotel_errors[hotel_name]["status"] = "completed"
        
        # Look for specific error patterns
        for hotel_name in list(hotel_errors.keys()):
            # Check for no data errors
            if no_data_pattern.search(line) and hotel_name in line:
                hotel_errors[hotel_name]["status"] = "failed"
                hotel_errors[hotel_name]["errors"].append("No rooms found")
            
            # Check for timeout errors
            if timeout_pattern.search(line) and hotel_name in line:
                hotel_errors[hotel_name]["status"] = "failed"
                hotel_errors[hotel_name]["errors"].append("Timeout waiting for room rows")
            
            # Check for no availability message
            if no_availability_pattern.search(line) and hotel_name in line:
                hotel_errors[hotel_name]["status"] = "no_availability"
                hotel_errors[hotel_name]["errors"].append("No availability")
            
            # Check for JS extraction failures
            js_failure_match = js_extraction_failed_pattern.search(line)
            if js_failure_match and hotel_name in line:
                error_reason = js_failure_match.group(1)
                hotel_errors[hotel_name]["errors"].append(f"JS extraction failed: {error_reason}")
            
            # Check for navigation errors
            nav_error_match = navigation_error_pattern.search(line)
            if nav_error_match and hotel_name in line:
                error_reason = nav_error_match.group(1)
                hotel_errors[hotel_name]["errors"].append(f"Navigation error: {error_reason}")
            
            # Check for successful extractions
            success_match = hotel_data_success_pattern.search(line)
            if success_match and hotel_name in line:
                rooms_count = int(success_match.group(1))
                if rooms_count > 0:
                    hotel_errors[hotel_name]["status"] = "success"
                    hotel_errors[hotel_name]["rooms_count"] = rooms_count
    
    # Also scan for generic error messages that might be related to hotels
    for hotel_name in list(hotel_errors.keys()):
        for line in log_lines:
            if "ERROR" in line and hotel_name in line:
                error_msg_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - ERROR - \w+ - (.*)', line)
                if error_msg_match:
                    error_msg = error_msg_match.group(1)
                    hotel_errors[hotel_name]["errors"].append(error_msg)
                    hotel_errors[hotel_name]["status"] = "failed"
    
    # Compile the list of hotels with failures
    for hotel_name, data in hotel_errors.items():
        # Consider any hotel with status "failed", "processing", or no rooms found as a failure
        is_failure = (
            data["status"] in ["failed", "processing"] or
            (data.get("status") == "success" and data.get("rooms_count", 0) == 0)
        )
        
        if is_failure:
            failures.append({
                "hotel_name": hotel_name,
                "failure_reason": "; ".join(data["errors"]) if data["errors"] else "Unknown failure"
            })
    
    return failures

def analyze_failures_with_gpt(failures: List[Dict[str, str]]) -> str:
    """
    Uses GPT to analyze the extraction failures and provide insights.

    Args:
        failures (List[Dict[str, str]]): A list of dictionaries describing failure details.
        
    Returns:
        str: The analysis generated by GPT.
    """
    if not failures:
        return "No extraction failures were found in the most recent scraping session."
    
    # Prepare a summary of failure examples for GPT.
    failure_examples = "\n".join([
        f"Hotel: {f['hotel_name']}, Reason: {f['failure_reason']}"
        for f in failures[:10]  # Limit to the first 10 examples.
    ])
    
    prompt = f"""
You are analyzing failures in a Booking.com web scraper's most recent run. The scraper failed to extract data for these hotels:

{failure_examples}

{"..." if len(failures) > 10 else ""}

Total extraction failures: {len(failures)}

Please identify:
1. Common patterns in these failures
2. Likely root causes
3. Specific recommendations to improve the scraper's reliability

Focus on technical solutions relevant to web scraping. Common issues may include:
- JS rendering problems
- Rate limiting or blocking by the website
- Selector changes on the website
- Timeout issues
- Network problems
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error analyzing failures with GPT: {e}\n\nPlease review the failure list manually."

def main() -> None:
    """Main function to run the extraction failure analyzer."""
    print("Extraction Failure Analyzer for Booking.com Scraper")
    print("=" * 60)
    print("Analyzing only the most recent scraping session")
    
    # Retrieve the latest scraper log (used for both error and main log analysis).
    error_log, main_log = get_latest_logs()
    if not main_log:
        print("No log file found. Cannot analyze extraction failures.")
        return
    
    print(f"Analyzing log file: {os.path.basename(main_log)}")
    
    # Find extraction failures by scanning the most recent session in the log file.
    failures = find_extraction_failures(error_log, main_log)
    
    print(f"\nFound {len(failures)} hotels with extraction failures in the most recent session.")
    
    if failures:
        print("\n=== EXTRACTION FAILURES ===")
        for i, failure in enumerate(failures, 1):
            print(f"{i}. {failure['hotel_name']}: {failure['failure_reason']}")
        
        print("\n=== ANALYSIS ===")
        print("Analyzing failures...")
        analysis = analyze_failures_with_gpt(failures)
        print("\n" + analysis)
        
        # Save failures and analysis to a text file.
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(LOG_DIR, f"extraction_failures_{timestamp}.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=== EXTRACTION FAILURES ===\n")
            f.write(f"Total: {len(failures)} in most recent session\n\n")
            for i, failure in enumerate(failures, 1):
                f.write(f"{i}. {failure['hotel_name']}: {failure['failure_reason']}\n")
            f.write("\n=== ANALYSIS ===\n")
            f.write(analysis)
        
        print(f"\nFailure report saved to: {output_file}")
    else:
        print("No extraction failures found in the most recent session. All hotels were processed successfully.")

if __name__ == "__main__":
    main()
