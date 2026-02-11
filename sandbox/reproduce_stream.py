
import sys
import os
import time
from threading import Event

# Add project root to path
sys.path.insert(0, r"d:\aquatrade")

from server.visualization_api import BacktestVisualizationAPI
from config.logger import get_logger

# Configure logging
import logging
logging.basicConfig(level=logging.DEBUG)

def test_backtest_stream():
    api = BacktestVisualizationAPI()
    stop_event = Event()
    
    # Use a known strategy and date range
    strategy_name = "apex_convergence_v1" # Or another valid strategy
    start_date = "2024-01-01"
    end_date = "2024-02-01" 
    
    print(f"Starting backtest stream for {strategy_name}...")
    
    try:
        stream = api.stream_backtest(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            stop_event=stop_event
        )
        
        trade_count = 0
        event_counts = {}
        
        for update in stream:
            event_type = update.get('type')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if event_type == 'new_trade':
                trade_count += 1
                print(f"Trade received: {update['data'].get('symbol')} {update['data'].get('action')} @ {update['data'].get('date')}")
            elif event_type == 'error':
                print(f"ERROR: {update['data']}")
                with open("d:\\aquatrade\\error.txt", "w") as f:
                    f.write(str(update['data']))
                
        print("\nStream finished.")
        print(f"Total trades received: {trade_count}")
        print(f"Event counts: {event_counts}")
        
    except Exception as e:
        import traceback
        with open("d:\\aquatrade\\traceback.log", "w") as f:
            f.write(traceback.format_exc())
        print("An error occurred. Check traceback.log")


if __name__ == "__main__":
    test_backtest_stream()
