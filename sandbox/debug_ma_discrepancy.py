
import pandas as pd
import numpy as np
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.utils.price_adjustment import apply_forward_adjustment

def analyze_discrepancy():
    target_code = "601988"
    start_date = "2024-06-01"
    end_date = "2024-08-15"
    
    dq = OptimizedStockDataQuery()
    
    # 1. Fetch data (now automatically adjusted by the fix)
    history = dq.get_batch_stock_history(
        [target_code],
        start_date,
        end_date,
        columns=['stock_code', 'trade_date', 'open', 'close', 'adj_factor']
    )
    history = history.sort_values('trade_date').reset_index(drop=True)
    
    # history_qfq = apply_forward_adjustment(history.copy()) # No longer needed if fix works
    history_qfq = history.copy()
    
    # 3. Calculate MA5 and MA10 on QFQ Close
    history_qfq['ma5'] = history_qfq['close'].rolling(5).mean()
    history_qfq['ma10'] = history_qfq['close'].rolling(10).mean()
    history_qfq['diff'] = history_qfq['ma5'] - history_qfq['ma10']
    
    # 4. Check for Death Cross
    history_qfq['prev_diff'] = history_qfq['diff'].shift(1)
    
    # Death Cross: prev_diff >= 0 and diff < 0
    death_crosses = history_qfq[(history_qfq['prev_diff'] >= 0) & (history_qfq['diff'] < 0)]
    
    # Golden Cross: prev_diff <= 0 and diff > 0
    golden_crosses = history_qfq[(history_qfq['prev_diff'] <= 0) & (history_qfq['diff'] > 0)]
    
    print("="*80)
    print(f"数据分析: {target_code} (2024-06-01 至 2024-08-15)")
    print("="*80)
    
    # Print dividend detection
    history['prev_factor'] = history['adj_factor'].shift(1)
    div_days = history[history['adj_factor'] != history['prev_factor']].dropna()
    print("因子变动 (分红/拆股):")
    for _, row in div_days.iterrows():
        print(f"  日期: {row['trade_date']}, 前因子: {row['prev_factor']}, 现因子: {row['adj_factor']}")
    
    print("\n死叉 (Death Cross) 触发记录:")
    for _, row in death_crosses.iterrows():
        print(f"  T日(信号): {row['trade_date']}, MA5: {row['ma5']:.4f}, MA10: {row['ma10']:.4f}, Diff: {row['diff']:.6f}")
        
    print("\n金叉 (Golden Cross) 触发记录:")
    for _, row in golden_crosses.iterrows():
        print(f"  T日(信号): {row['trade_date']}, MA5: {row['ma5']:.4f}, MA10: {row['ma10']:.4f}, Diff: {row['diff']:.6f}")

    print("\n7月23日 前后明细:")
    focus_dates = history_qfq[(history_qfq['trade_date'] >= '2024-07-20') & (history_qfq['trade_date'] <= '2024-07-25')]
    for _, row in focus_dates.iterrows():
        print(f"  {row['trade_date']} | Close(QFQ): {row['close']:.4f} | MA5: {row['ma5']:.4f} | MA10: {row['ma10']:.4f} | Diff: {row['diff']:.6f}")

if __name__ == "__main__":
    analyze_discrepancy()
