import pandas as pd
import numpy as np
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import os

def diagnose_002717():
    dq = OptimizedStockDataQuery()
    symbol = "2717" # Search without leading zeros as found in DB
    target_date = "2024-05-24"
    
    # Check what codes exist
    check_query = f"SELECT stock_code FROM stock_info WHERE stock_name LIKE '%岭南控股%'"
    found_codes = dq._query_df(check_query)
    print(f"Found codes for 岭南控股: {found_codes['stock_code'].tolist()}")
    if not found_codes.empty:
        symbol = str(found_codes['stock_code'].iloc[0])
    
    # Load history including target date
    start_date = "2024-05-10"
    hist = dq.get_stock_history(symbol, start_date, target_date)
    if hist.empty:
        print(f"ERROR: No history found for {symbol} between {start_date} and {target_date}")
        return
        
    print(f"--- History for {symbol} ({target_date}) ---")
    print(hist.tail(3)[['trade_date', 'close', 'adj_factor']])
    
    # Calculate MA5 on RAW prices (Strategy Path)
    raw_close = hist['close'].values.reshape(-1, 1).astype(np.float32)
    from core.calc import vectorized_ops as ops
    ma5_raw = ops.calc_ma_vectorized(raw_close, 5)
    
    # Calculate MA5 on QFQ prices (Engine Execution Path)
    from core.utils.price_adjustment import apply_forward_adjustment
    hist_qfq = apply_forward_adjustment(hist.copy())
    qfq_close = hist_qfq['close'].values.reshape(-1, 1).astype(np.float32)
    ma5_qfq = ops.calc_ma_vectorized(qfq_close, 5)
    
    t_idx = list(hist['trade_date']).index(target_date)
    
    print(f"\n【诊断 002717 @ {target_date}】")
    print(f"Vectorized Path (Signal Gen):")
    print(f"  > Used Close (RAW): {raw_close[t_idx, 0]}")
    print(f"  > Calc MA5 (RAW):   {ma5_raw[t_idx, 0]}")
    print(f"  > Decision (Close < MA5): {raw_close[t_idx, 0] < ma5_raw[t_idx, 0]}")
    
    print(f"\nExecution Path (Trade Matching):")
    print(f"  > Used Close (QFQ): {qfq_close[t_idx, 0]}")
    print(f"  > Calc MA5 (QFQ):   {ma5_qfq[t_idx, 0]}")
    print(f"  > Decision (Close < MA5): {qfq_close[t_idx, 0] < ma5_qfq[t_idx, 0]}")
    
    # Check if signal timing was shifted (T+1)
    if t_idx > 0:
        prev_close = raw_close[t_idx-1, 0]
        prev_ma5 = ma5_raw[t_idx-1, 0]
        print(f"\nPrevious Day ({hist.iloc[t_idx-1]['trade_date']}) Signal:")
        print(f"  > RAW Close: {prev_close}")
        print(f"  > RAW MA5:   {prev_ma5}")
        print(f"  > Signal (T-1): {prev_close < prev_ma5}")

if __name__ == "__main__":
    diagnose_002717()
