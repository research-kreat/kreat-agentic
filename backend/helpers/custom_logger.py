"""
HOW TO USE

def sample_run():
    # Task 1: Mongo Connection
    start1 = print_start_time()
    print_end_time(start1, "Mongo Connection")

    # Task 2: API Call
    start2 = print_start_time()
    print_end_time(start2, "API Call")

    # Save all logs to CSV
    flush_log_row_to_csv()
"""

import os
import csv
import time
from datetime import datetime

# ANSI color codes
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"

# Global log dictionary for one run
LOG_ROW = {}

def print_start_time():
    start = datetime.now()
    print(f"{BLUE}[START]{RESET} {start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    return start

def print_end_time(start_time, task_name=None):
    end = datetime.now()
    duration = end - start_time
    duration_ms = int(duration.total_seconds() * 1000)
    print(f"{BLUE}[END]{RESET} {end.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Duration: {duration_ms} ms)")

    if task_name:
        LOG_ROW[task_name] = f"{duration_ms} ms"

def flush_log_row_to_csv(user_input):
    if not LOG_ROW:
        return

    csv_path = "helpers/TimeReport.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    existing_rows = []
    headers = []

    # Load existing CSV if present
    if os.path.exists(csv_path):
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            existing_rows = list(reader)

    # Ensure "User Input" is in headers
    if "User Input" not in headers:
        headers.insert(0, "User Input")

    # Add new keys from LOG_ROW to headers if needed
    for key in LOG_ROW:
        if key not in headers:
            headers.append(key)

    # Prepare a new row
    new_row = {col: "" for col in headers}
    new_row["User Input"] = user_input
    for key, value in LOG_ROW.items():
        new_row[key] = value

    existing_rows.append(new_row)

    # Write back the updated CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(existing_rows)

    LOG_ROW.clear()

# Logger helpers
def log_info(msg): print(f"{BLUE}[INFO]{RESET} {msg}")
def log_success(msg): print(f"{GREEN}[SUCCESS]{RESET} {msg}")
def log_warning(msg): print(f"{YELLOW}[WARNING]{RESET} {msg}")
def log_error(msg): print(f"{RED}[ERROR]{RESET} {msg}")