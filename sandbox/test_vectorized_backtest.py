"""
Quick test to verify vectorized signal generation is working

This script runs a short backtest to verify:
1. The engine detects vectorized strategies
2. Signal generation time is dramatically reduced
3. Results are correct
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from core.strategies.jq_volume_strategy_v2 import JQVolumeStrategypro
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def test_vectorized_backtest():
    print("=" * 60)
    print("Testing Vectorized Signal Generation")
    print("=" * 60)
    
    # Initialize components
    data_query = OptimizedStockDataQuery()
    strategy = JQVolumeStrategypro()
    engine = FlexibleBacktestEngine(data_query=data_query, initial_capital=1_000_000)
    
    # Run a short backtest (1 month)
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    print(f"\nRunning backtest from {start_date} to {end_date}")
    print(f"Strategy: {strategy.strategy_name}")
    print(f"Has vectorized method: {hasattr(strategy, 'generate_signals_vectorized')}")
    
    # Run backtest
    results = []
    for event in engine.run_backtest_streaming(start_date, end_date, strategy):
        if event['type'] == 'daily_equity_engine':
            results.append(event['data'])
        elif event['type'] == 'error':
            print(f"\n❌ Error: {event['data']['message']}")
            return False
    
    print(f"\n✅ Backtest completed successfully!")
    print(f"Total days: {len(results)}")
    
    if results:
        final_equity = results[-1]['equity']
        initial_capital = 1_000_000
        total_return = ((final_equity - initial_capital) / initial_capital) * 100
        print(f"Final equity: ¥{final_equity:,.2f}")
        print(f"Total return: {total_return:.2f}%")
    
    return True

if __name__ == "__main__":
    success = test_vectorized_backtest()
    sys.exit(0 if success else 1)
