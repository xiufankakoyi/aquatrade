"""
用Tushare API验证指数数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tushare as ts
import pandas as pd
from config.config import Config

ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

start_date = "20240101"
end_date = "20251231"

indices = [
    ('000001.SH', '上证指数'),
    ('000852.SH', '中证1000'),
    ('000300.SH', '沪深300'),
    ('000905.SH', '中证500'),
]

print("=" * 70)
print("Tushare API 指数数据验证")
print("=" * 70)

for ts_code, name in indices:
    df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    
    if df.empty:
        print(f"{name}({ts_code}): 无数据")
        continue
    
    df = df.sort_values('trade_date')
    
    first_close = df['close'].iloc[0]
    last_close = df['close'].iloc[-1]
    total_return = (last_close - first_close) / first_close * 100
    
    print(f"\n{name}({ts_code}):")
    print(f"  数据范围: {df['trade_date'].iloc[0]} 到 {df['trade_date'].iloc[-1]}")
    print(f"  数据点数: {len(df)}")
    print(f"  起始价格: {first_close:.2f}")
    print(f"  结束价格: {last_close:.2f}")
    print(f"  总收益: {total_return:.2f}%")
