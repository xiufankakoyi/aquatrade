"""
QuestDB Import Progress Monitor
===============================
Visualizes import progress for 'factors_valuation' and detects stalls.

Usage:
    python scripts/monitor_import_progress.py
"""

import requests
import time
import sys
from datetime import datetime

QUESTDB_HOST = "localhost"
QUESTDB_HTTP_PORT = 9000
TABLE_NAME = "factors_valuation"
TARGET_ROWS = 6841370
POLL_INTERVAL = 3  # seconds

def get_row_count():
    try:
        url = f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec"
        resp = requests.get(url, params={"query": f"select count() from {TABLE_NAME}"}, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            if 'dataset' in data and data['dataset']:
                return data['dataset'][0][0]
    except Exception:
        pass
    return -1

def format_time(seconds):
    if seconds < 0: return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def monitor():
    print(f"\n🔍 QuestDB Import Monitor: {TABLE_NAME}")
    print(f"🎯 Target Rows: {TARGET_ROWS:,}")
    print("-" * 60)

    start_time = time.time()
    last_count = -1
    last_change_time = start_time
    
    # Initial fetch
    current_count = get_row_count()
    start_count = max(0, current_count) # In case we start monitoring mid-way
    
    # If starting from 0, use exact start time. If mid-way, speed calc might be rough initially.
    
    while True:
        try:
            current_count = get_row_count()
            
            if current_count == -1:
                print("\r⚠️  Connection lost... retrying", end="")
                time.sleep(POLL_INTERVAL)
                continue

            # Calculate metrics
            elapsed = time.time() - start_time
            imported_session = current_count - start_count
            
            # Overall speed (rows/sec) - using session average for stability
            speed = imported_session / elapsed if elapsed > 1 else 0
            
            # Progress
            percent = (current_count / TARGET_ROWS) * 100
            
            # ETA
            remaining_rows = TARGET_ROWS - current_count
            eta_seconds = remaining_rows / speed if speed > 10 else -1
            
            # Stall detection
            if current_count > last_count:
                last_change_time = time.time()
                stall_status = "🟢 Running"
            else:
                stall_duration = time.time() - last_change_time
                if stall_duration > 60:
                    stall_status = f"🔴 STALLED ({int(stall_duration)}s)"
                elif stall_duration > 15:
                    stall_status = f"🟡 Slow ({int(stall_duration)}s)"
                else:
                    stall_status = "🟢 Running"

            last_count = current_count

            # Progress Bar
            bar_len = 30
            filled_len = int(bar_len * percent / 100)
            bar = '█' * filled_len + '░' * (bar_len - filled_len)

            # Output
            # Clear line is handled by \r, but we print a multiline or single line status
            status_line = (
                f"\r{bar} {percent:5.1f}% | "
                f"Cnt: {current_count:,} | "
                f"Spd: {int(speed):,}/s | "
                f"ETA: {format_time(eta_seconds)} | "
                f"{stall_status}    " 
            )
            
            sys.stdout.write(status_line)
            sys.stdout.flush()

            if current_count >= TARGET_ROWS:
                print("\n\n✅ Import Complete!")
                break
                
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped.")
            break

if __name__ == "__main__":
    monitor()
