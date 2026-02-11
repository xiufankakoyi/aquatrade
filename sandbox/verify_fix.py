import pandas as pd
import numpy as np
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import os

def verify_fix():
    dq = OptimizedStockDataQuery()
    start_date = "2024-05-15"
    end_date = "2024-05-25"
    symbol_str = "524" # 岭南控股
    
    print(f"--- Testing get_all_daily_data_for_period (Actual Backtest Path) ---")
    # This is the call that was previously returning Raw prices
    df = dq.get_all_daily_data_for_period(start_date, end_date)
    
    if df.empty:
        print("ERROR: No data returned.")
        return
        
    # Check specific stock row for the target date
    target_date = "2024-05-24"
    row = df[(df['stock_code'] == symbol_str) & (df['trade_date'] == target_date)]
    
    if row.empty:
        # Try numeric variant as backup though codes in df should be strings
        print(f"Warning: Stock {symbol_str} not found in dataframe. Available codes sample: {df['stock_code'].unique()[:5]}")
        row = df[(df['stock_code'].astype(str) == symbol_str) & (df['trade_date'] == target_date)]

    if not row.empty:
        qfq_close = row['close'].values[0]
        adj_factor = row['adj_factor'].values[0]
        # Calculate what the raw close would have been if we reversed the adjustment
        estimated_raw = qfq_close / adj_factor
        
        print(f"\n【验证结果 @ {target_date}】")
        print(f"  > Stock Code in DataFrame: {row['stock_code'].values[0]}")
        print(f"  > Adjusted Close (Result): {qfq_close}")
        print(f"  > Adjustment Factor:        {adj_factor}")
        print(f"  > Observed Scale:           {'QFQ (Adjusted)' if qfq_close > 20 else 'RAW (Unadjusted)'}")
        
        if qfq_close > 20: 
            print("\n✅ SUCCESS: The loader is now providing Adjusted (QFQ) prices for signal generation.")
        else:
            print("\n❌ FAILURE: The loader is still providing Raw prices.")
    else:
        print(f"ERROR: Could not find 002717 in the returned data specifically for {target_date}.")

if __name__ == "__main__":
    verify_fix()
