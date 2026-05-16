"""
详细调试2025年1月2号的情况
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import pandas as pd
import numpy as np

query = OptimizedStockDataQuery()

# 检查2025-01-02是否是交易日
print("=" * 60)
print("检查2025-01-02是否是交易日")
print("=" * 60)

trading_dates = query.get_trading_dates('2024-12-30', '2025-01-10')
print(f"交易日列表: {trading_dates}")
print(f"2025-01-02是否是交易日: {'2025-01-02' in trading_dates}")

# 检查数据
print("\n" + "=" * 60)
print("检查2025-01-02的数据")
print("=" * 60)

# 直接查询数据
df = query.get_all_daily_data_for_period('2025-01-02', '2025-01-02')
if df is not None and len(df) > 0:
    print(f"2025-01-02有 {len(df)} 条股票数据")
    print(f"股票代码示例: {df['stock_code'].unique()[:5].tolist()}")
    
    # 检查均线数据
    if 'ma5' in df.columns:
        ma5_valid = df['ma5'].notna().sum()
        print(f"MA5有效数据: {ma5_valid}/{len(df)}")
    if 'ma10' in df.columns:
        ma10_valid = df['ma10'].notna().sum()
        print(f"MA10有效数据: {ma10_valid}/{len(df)}")
    if 'ma20' in df.columns:
        ma20_valid = df['ma20'].notna().sum()
        print(f"MA20有效数据: {ma20_valid}/{len(df)}")
else:
    print("2025-01-02没有数据!")

# 检查前一天2024-12-31的数据
print("\n" + "=" * 60)
print("检查前一天2024-12-31的数据（防止未来函数）")
print("=" * 60)

df_prev = query.get_all_daily_data_for_period('2024-12-31', '2024-12-31')
if df_prev is not None and len(df_prev) > 0:
    print(f"2024-12-31有 {len(df_prev)} 条股票数据")
    
    # 检查均线多头排列
    if all(col in df_prev.columns for col in ['ma5', '