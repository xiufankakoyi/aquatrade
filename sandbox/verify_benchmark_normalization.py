
import sys
import os
import pandas as pd
from pathlib import Path

# Add project root to sys.path
project_root = r"d:\aquatrade"
sys.path.insert(0, project_root)

from server.visualization_api import BacktestVisualizationAPI
from config.config import Config

def verify_benchmark():
    try:
        api = BacktestVisualizationAPI()
        
        # Manually trigger the logic inside _get_benchmark_data_from_db and the normalization logic 
        # that mimics stream_backtest or _extract_equity_curve_from_df
        
        print(f"Initial Capital from Config: {Config.INITIAL_CAPITAL}")
        
        # Test parameters
        start_date = "2024-01-01"
        end_date = "2024-06-01"
        benchmark_code = "000300"
        
        # 1. Get raw data
        df = api._get_benchmark_data_from_db(benchmark_code, start_date, end_date)
        if df.empty:
            print("ERROR: No benchmark data found.")
            return

        print(f"Raw Benchmark Data Head:\n{df.head()}")
        
        # 2. Simulate Normalization Logic from visualization_api.py
        # Logic from _extract_equity_curve_from_df / stream_backtest
        
        # Assume these are the trading dates (simplified)
        dates = df['date'].tolist()
        
        strategy_dates_df = pd.DataFrame({'date': dates})
        merged_df = pd.merge(strategy_dates_df, df, on='date', how='left')
        merged_df['close'] = merged_df['close'].ffill().bfill()
        
        first_valid_benchmark = merged_df['close'].dropna().iloc[0]
        print(f"First Valid Benchmark Value: {first_valid_benchmark}")
        
        if first_valid_benchmark > 0:
            normalized_curve = (merged_df['close'] / first_valid_benchmark) * Config.INITIAL_CAPITAL
            benchmark_curve = normalized_curve.fillna(Config.INITIAL_CAPITAL).tolist()
            
            print(f"Normalized Start Value: {benchmark_curve[0]}")
            print(f"Normalized End Value: {benchmark_curve[-1]}")
            
            if abs(benchmark_curve[0] - Config.INITIAL_CAPITAL) < 1.0:
                 print("SUCCESS: Benchmark normalized correctly to Initial Capital.")
            else:
                 print(f"FAILURE: Benchmark start value {benchmark_curve[0]} does not match Initial Capital {Config.INITIAL_CAPITAL}")
        else:
            print("FAILURE: First valid benchmark is <= 0")

    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_benchmark()
