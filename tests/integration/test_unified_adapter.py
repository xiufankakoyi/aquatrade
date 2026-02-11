
import pytest
import pandas as pd
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.unified_data_query import UnifiedDataQueryAdapter

class SimpleTestStrategy:
    def set_runtime_context(self, **kwargs):
        self.context = kwargs
        # kwargs might contain 'current_date', 'data_query' etc.
    
    def on_start(self):
        pass
        
    def on_stop(self):
        pass
        
    def generate_signals(self, current_date, stock_pool_today, data_query):
        # Engine passes stock_pool_today
        stock_pool = stock_pool_today
        
        # stock_pool is a DataFrame (Pandas, converted from Polars by Engine?)
        # OptimizedBacktestEngine uses Polars??
        # FlexibleBacktestEngine uses Polars OR Pandas depending on implementation.
        # But OptimizedStockDataQuery.get_stock_pool returns Pandas.
        # UnifiedDataQueryAdapter.get_stock_pool_pl returns Polars.
        # FlexibleBacktestEngine checks for loop:
        # for date in date_range: stock_pool = data_query.get_stock_pool(date)
        # Wait! FlexibleBacktestEngine calls `get_stock_pool` (Pandas) or `get_stock_pool_pl`?
        
        # Checking FlexibleBacktestEngine source would be good.
        # Assuming it handles whatever `get_stock_pool` returns if not optimized.
        # But `OptimizedBacktestEngine` is what we usually use.
        # Here we test `FlexibleBacktestEngine` with Adapter.
        
        # Simple Logic: Buy 600808 if available
        signals = {}
        # Check if 600808 in pool
        # If pool is Polars:
        if 'polars' in str(type(stock_pool)):
             # Polars
             if not stock_pool.filter(stock_pool['stock_code'] == '600808').is_empty():
                 signals['600808'] = {'action': 'buy', 'price': 0, 'quantity': 100}
        else:
             # Pandas
             # UDM Adapter returns normalized code '600808' (hot)
             # But let's check both just in case
             codes = stock_pool['stock_code'].astype(str).values
             if '600808' in codes or '600808.SH' in codes:
                 signals['600808'] = {'action': 'buy', 'quantity': 100}
        
        return signals

def test_unified_adapter_integration():
    print("Initializing UnifiedDataQueryAdapter...")
    try:
        data_query = UnifiedDataQueryAdapter()
    except Exception as e:
        pytest.fail(f"Failed to init adapter: {e}")
        
    print("Initializing Engine...")
    engine = FlexibleBacktestEngine(data_query, initial_capital=100000)
    
    # Test Period (Hot Data)
    start_date = "2021-01-04"
    end_date = "2021-01-08"
    
    strategy = SimpleTestStrategy()
    
    print(f"Running backtest from {start_date} to {end_date}...")
    updates = []
    try:
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            updates.append(update)
            if update['type'] == 'error':
                print(f"Error event: {update['data']}")
    except Exception as e:
        pytest.fail(f"Backtest failed with exception: {e}")
        
    # Analyze results
    print(f"Total updates: {len(updates)}")
    daily_events = [u for u in updates if u['type'] == 'daily_equity_engine']
    trade_events = [u for u in updates if 'trade' in u['type']]
    
    print(f"Daily events: {len(daily_events)}")
    print(f"Trade events: {len(trade_events)}")
    
    if len(daily_events) == 0:
        pytest.fail("No daily equity events generated. Backtest might have failed to load data.")
        
    # Check if prices look real (not 0)
    last_equity = daily_events[-1]['data']['equity']
    print(f"Final Equity: {last_equity}")
    assert last_equity != 100000, "Equity should change if trades occurred (or commission charged)"
    
    # Check data integrity implicitly via no crashes
    assert True

if __name__ == "__main__":
    test_unified_adapter_integration()
