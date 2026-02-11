import sys
import os
import time
import pandas as pd
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

# Mock Strategy
class MockStrategy:
    def __init__(self):
        self.strategy_name = "MockStrategy"
    def set_runtime_context(self, **kwargs): pass
    def generate_signals(self, current_date, stock_pool_today, data_query):
        return {}

def reproduce():
    print(">>> Initializing Data Query...")
    data_query = OptimizedStockDataQuery()
    
    print(">>> Initializing Engine...")
    engine = FlexibleBacktestEngine(data_query=data_query)
    
    strategy = MockStrategy()
    start_date = '2024-05-20'
    end_date = '2024-05-25'
    
    print(f">>> Running Backtest ({start_date} to {end_date})...")
    
    try:
        gen = engine.run_backtest_streaming(start_date, end_date, strategy)
        for update in gen:
            print(f"Received Update: {update['type']}")
            if update['type'] == 'daily_equity_engine':
                data = update['data']
                # Check for the keys that were causing issues
                if 'strategyReturn' not in data:
                    print("!!! FAIL: 'strategyReturn' missing in daily_equity_engine")
                    print(f"Data keys: {data.keys()}")
                    return
                if 'equity' not in data:
                    print("!!! FAIL: 'equity' missing in daily_equity_engine")
                    return
            elif update['type'] == 'error':
                print(f"!!! ERROR: {update['data']['message']}")
                return
                
        print(">>> Backtest Completed Successfully")
        
    except Exception as e:
        print(f"!!! EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduce()
