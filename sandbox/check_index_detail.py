"""
检查指数数据的详细情况
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tushare as ts
import pandas as pd
from config.config import Config

ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

print("=" * 70)
print("检查指数数据详情")
print("=" * 70)

indices = [
    ('000001.SH', '上证指数'),
    ('000852.SH', '中证1000'),
]

for ts_code, name in indices:
    df = pro.index_daily(ts_code=ts_code, start_date='20240101', end_date='20251231')
    df = df.sort_values('trade_date')
    
    print(f"\n{name}({ts_code}):")
    print(f"  数据范围: {df['trade_date'].iloc[0]} 到 {df['trade_date'].iloc[-1]}")
    
    print(f"\n  最近10天数据:")
    print(df[['trade_date', 'close', 'pct_chg']].tail(10).to_string(index=False))
    
    print(f"\n  2024年收益:")
    df_2024 = df[df['trade_date'].str.startswith('2024')]
    if len(df_2024) > 0:
        first_2024 = df_2024['close'].iloc[0]
        last_2024 = df_2024['close'].iloc[-1]
        ret_2024 = (last_2024 - first_2024) / first_2024 * 100
        print(f"    {df_2024['trade_date'].iloc[0]} 到 {df_2024['trade_date'].iloc[-1]}")
        print(f"    收益: {ret_2024:.2f}%")
    
    print(f"\n  2025年收益:")
    df_2025 = df[df['trade_date'].str.startswith('2025')]
    if len(df_2025) > 0:
        first_2025 = df_2025['close'].iloc[0]
        last_2025 = df_2025['close'].iloc[-1]
        ret_2025 = (last_2025 - first_2025) / first_2025 * 100
        print(f"    {df_2025['trade_date'].iloc[0]} 到 {df_2025['trade_date'].iloc[-1]}")
        print(f"    收益: {ret_2025:.2f}%")
