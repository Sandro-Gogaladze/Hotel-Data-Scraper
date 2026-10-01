"""
Process-based extraction module for Booking.com hotel details.

This module defines functions that launch a new Playwright instance in a separate process
to extract detailed hotel data using the existing extraction logic. Each worker process handles 
multiple hotels using a single browser instance for better performance.
"""

import concurrent.futures
import os
import sys
import time
import multiprocessing
from typing import List, Dict, Any, Callable, Optional

# Ensure the project root is in sys.path for correct module resolution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from playwright.sync_api import sync_playwright  # type: ignore
from utils.logger import log_message
from utils.anti_detection import get_browser_launch_options, add_random_delay
from scraper.hotel_page.detailed_extractor import extract_detailed_info
from config import MAX_WORKERS, HEADLESS, URL_LOADING_REFRESH_TIMEOUT

def worker_process_queue(task_queue, result_queue, worker_id: int, storage_state: Optional[Dict[str, Any]] = None):
    """
    Worker process that takes hotels from a queue and processes them one by one
    using a SINGLE browser and SINGLE page instance for all hotels. This improves performance
    by avoiding the overhead of browser/page startup/shutdown for each hotel.

    Args:
        task_queue: A multiprocessing queue containing hotel dictionaries to process
        result_queue: A multiprocessing queue to store processed hotel results
        worker_id (int): The ID of this worker for logging purposes
        storage_state: The run's pinned session cookies (see scraper/session.py), so every
            worker sees the same version of the site; None for a fresh session
    """
    log_message(f"[Worker #{worker_id}] Starting worker process", "info")
    log_message(f"[Worker #{worker_id}] URL loading refresh timeout: {URL_LOADING_REFRESH_TIMEOUT}s", "debug")
    hotels_processed = 0

    try:
        # Launch a single Playwright instance for this worker
        # This browser will be reused for ALL hotels processed by this worker
        with sync_playwright() as p:
            # Stagger worker startup to avoid simultaneous requests
            startup_delay = worker_id * 2.0  # Each worker waits 2 seconds more than the previous
            if startup_delay > 0:
                log_message(f"[Worker #{worker_id}] Staggering startup by {startup_delay}s to avoid detection", "debug")
                time.sleep(startup_delay)
            
            # Use anti-detection browser options with worker-specific settings
            launch_options = get_browser_launch_options(headless=HEADLESS, worker_id=worker_id)
            browser = p.chromium.launch(**launch_options)
            log_message(f"[Worker #{worker_id}] Browser launched successfully", "info")
            # Create a single page for this worker, in the run's pinned session
            page = browser.new_context(storage_state=storage_state).new_page()
            
            # Configure the page to handle slow loading URLs
            page.set_default_timeout(60000)  # 60 seconds total timeout
            
            # Process hotels from the queue until it's empty
            while True:
                try:
                    # Try to get a hotel from the queue with a timeout
                    # This allows the worker to exit if the queue is empty
                    hotel = task_queue.get(timeout=1.0)
                    
                    hotel_name = hotel.get("Hotel Name", "Unknown hotel")
                    hotel_index = hotel.get("Index", "N/A")
                    
                    log_message(f"[Worker #{worker_id}] Processing hotel #{hotel_index}: {hotel_name}", "info")
                    
                    try:
                        # Add random delay between hotels, with worker-specific variation
                        base_delay = 1.5 + (worker_id * 0.5)  # Each worker has slightly different timing
                        add_random_delay(base_delay, base_delay + 2.0)
                        
                        # Pass the same page to each extraction
                        updated_hotel = extract_detailed_info(browser, hotel, page=page)
                        result_queue.put(updated_hotel)
                        hotels_processed += 1
                        log_message(f"[Worker #{worker_id}] Completed hotel #{hotel_index}: {hotel_name} (total: {hotels_processed})", "info")
                    except Exception as e:
                        error_msg = f"[Worker #{worker_id}] Error extracting details for hotel #{hotel_index}: {hotel_name} - {e}"
                        log_message(error_msg, "error")
                        hotel.update({"Error": error_msg})
                        result_queue.put(hotel)
                        hotels_processed += 1
                        
                except multiprocessing.queues.Empty:
                    # Queue is empty, exit the loop
                    log_message(f"[Worker #{worker_id}] No more hotels in queue, exiting", "info")
                    break
                except Exception as e:
                    log_message(f"[Worker #{worker_id}] Error getting hotel from queue: {e}", "error")
                    # Brief pause to avoid tight loop if there's an issue
                    time.sleep(0.1)
            
            # Close the browser when we're done with all hotels
            log_message(f"[Worker #{worker_id}] Closing browser after processing {hotels_processed} hotels", "info")
            page.close()
            browser.close()
            
    except Exception as e:
        error_msg = f"[Worker #{worker_id}] Critical error: {e}"
        log_message(error_msg, "error")
    
    log_message(f"[Worker #{worker_id}] Worker completed after processing {hotels_processed} hotels", "info")
    return hotels_processed

def process_all_details_processes(
    hotels: List[Dict[str, Any]],
    max_workers: int = MAX_WORKERS,
    progress_callback: Optional[Callable[[int], None]] = None,
    storage_state: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Process a list of hotel dictionaries concurrently using a ProcessPoolExecutor with a queue system.
    Each worker process takes hotels from a shared queue, ensuring efficient utilization of resources.
    Workers run in TRUE PARALLEL execution, with each worker keeping a single browser instance open
    for processing all of its assigned hotels.

    Args:
        hotels (List[Dict[str, Any]]): A list of hotel dictionaries, each containing keys like
            "Hotel Name", "Hotel Link", and "Index".
        max_workers (int): The maximum number of concurrent processes to use (default from config).
        progress_callback (Optional[Callable[[int], None]]): Optional callback for progress updates.
        storage_state (Optional[Dict[str, Any]]): The run's pinned session cookies, shared with every worker.

    Returns:
        List[Dict[str, Any]]: The list of hotel dictionaries updated with detailed information.
    """
    if not hotels:
        return []
    
    # Limit max_workers to the number of hotels
    max_workers = min(max_workers, len(hotels))
    log_message(f"[ProcessPool] Starting parallel extraction using queue system with {max_workers} worker processes", "info")
    log_message(f"[ProcessPool] Each worker will maintain a SINGLE browser instance for all its hotels", "info")
    
    # Create queues for tasks and results
    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()
    
    # Add all hotels to the task queue
    for hotel in hotels:
        task_queue.put(hotel)
    
    log_message(f"[ProcessPool] Added {len(hotels)} hotels to task queue", "info")
    
    # Start worker processes
    processes = []
    for worker_id in range(max_workers):
        process = multiprocessing.Process(
            target=worker_process_queue,
            args=(task_queue, result_queue, worker_id, storage_state)
        )
        process.start()
        processes.append(process)
        log_message(f"[ProcessPool] Started worker process #{worker_id} (PID: {process.pid})", "debug")
    
    # Collect results
    all_results = []
    completed_count = 0
    total_hotels = len(hotels)
    
    # Show progress while waiting for results
    while completed_count < total_hotels:
        try:
            # Get results without blocking indefinitely
            try:
                result = result_queue.get(timeout=0.5)
                all_results.append(result)
                completed_count += 1
                
                # Log progress periodically
                if completed_count % max(1, total_hotels // 20) == 0 or completed_count == total_hotels:
                    log_message(f"[ProcessPool] Progress: {completed_count}/{total_hotels} hotels processed ({(completed_count/total_hotels)*100:.1f}%)", "info")
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed_count)
            except multiprocessing.queues.Empty:
                # No results yet, check if processes are still alive
                if not any(p.is_alive() for p in processes):
                    log_message("[ProcessPool] All worker processes have exited but not all hotels were processed", "warning")
                    break
                # Continue waiting
                continue
                
        except KeyboardInterrupt:
            log_message("[ProcessPool] Processing interrupted by user", "warning")
            break
    
    # Clean up processes
    for i, process in enumerate(processes):
        if process.is_alive():
            log_message(f"[ProcessPool] Terminating worker process #{i}", "debug")
            process.terminate()
        process.join(timeout=1.0)
    
    # Check if we got results for all hotels
    if len(all_results) != len(hotels):
        log_message(f"[ProcessPool] Warning: Expected {len(hotels)} results but got {len(all_results)}", "warning")
        
        # Add missing hotels with error message
        processed_indices = {result.get("Index") for result in all_results}
        for hotel in hotels:
            if hotel.get("Index") not in processed_indices:
                hotel.update({"Error": "Hotel processing was interrupted or failed to complete"})
                all_results.append(hotel)
    
    # Sort results to match original order
    result_dict = {result.get("Index", i+10000): result for i, result in enumerate(all_results)}
    sorted_results = [result_dict.get(hotel.get("Index", -1), hotel) for hotel in hotels]
    
    log_message(f"[ProcessPool] Completed extraction for {len(sorted_results)} hotels", "info")
    return sorted_results

def process_all_details_processes_with_progress(
    hotels: List[Dict[str, Any]], 
    progress_callback: Optional[Callable[[Optional[int], Optional[int]], None]] = None,
    max_workers: int = MAX_WORKERS,
    storage_state: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Process a list of hotel dictionaries concurrently with enhanced progress tracking.
    This function is specifically designed for FastAPI integration.

    Args:
        hotels (List[Dict[str, Any]]): A list of hotel dictionaries
        progress_callback: Callback function that accepts (total, current) parameters
        max_workers (int): The maximum number of concurrent processes to use
        storage_state (Optional[Dict[str, Any]]): The run's pinned session cookies

    Returns:
        List[Dict[str, Any]]: The list of hotel dictionaries updated with detailed information.
    """
    def internal_progress_callback(current: int):
        """Internal callback that calls the external one with both total and current."""
        if progress_callback:
            progress_callback(total=len(hotels), current=current)
    
    # Use the existing function with our internal callback
    return process_all_details_processes(
        hotels=hotels,
        max_workers=max_workers,
        progress_callback=internal_progress_callback,
        storage_state=storage_state
    )