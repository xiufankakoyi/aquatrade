"""
详细分析聚宽的交易逻辑
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path
import numpy as np
import pandas as pd

print("=" * 70)
print("详细分析聚宽交易逻辑")
print("=" * 70)

parquet_path = Path("data/parquet_data/stock_daily.parquet")

df = pl.scan_parquet(str(parquet_path)).filter(
    (pl.col('ts_code') == '000001.SZ') &
    (pl.col('trade_date') >= '2025-01-01') &
    (pl.col('trade_date') <= '2025-03-15')
).select(['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'adj_factor']).collect().sort('trade_date')

last_adj = df['adj_factor'].last()
df_adj = df.with_columns([
    (pl.col('close') * pl.col('adj_factor') / last_adj).alias('close_adj')
])

close_adj = df_adj['close_adj'].to_numpy()
dates = df_adj['trade_date'].to_numpy()
closes = df_adj['close'].to_numpy()

ma5 = pd.Series(close_adj).rolling(window=5).mean().values
ma10 = pd.Series(close_adj).rolling(window=10).mean().values

print("\n【聚宽交易记录】")
print("  2025-01-21 buy  (开盘价买入)")
print("  2025-01-24 sell (开盘价卖出)")
print("  2025-02-10 buy  (开盘价买入)")
print("  2025-02-27 sell (开盘价卖出)")

print("\n【聚宽逻辑推测】")
print("聚宽在T日开盘交易，说明信号是在T-1日收盘后生成的")
print("信号生成条件：收盘后计算MA，检查交叉")

print("\n【详细MA数据】")
print(f"{'日期':<12} {'收盘':<8} {'MA5':<10} {'MA10':<10} {'MA5>MA10':<10} {'备注'}")
print("-" * 70)

for i in range(len(dates)):
    date = dates[i]
    close = closes[i]
    m5 = ma5[i]
    m10 = ma10[i]
    
    if np.isnan(m5) or np.isnan(m10):
        print(f"{date:<12} {close:<8.2f} {'NaN':<10} {'NaN':<10}")
        continue
    
    ma5_gt_ma10 = m5 > m10
    note = ""
    
    # 标记聚宽交易日期
    if date == '2025-01-21':
        note = "← 聚宽买入日"
    elif date == '2025-01-24':
        note = "← 聚宽卖出日"
    elif date == '2025-02-10':
        note = "← 聚宽买入日"
    elif date == '2025-02-27':
        note = "← 聚宽卖出日"
    
    print(f"{date:<12} {close:<8.2f} {m5:<10.2f} {m10:<10.2f} {str(ma5_gt_ma10):<10} {note}")

print("\n【信号分析】")
print("聚宽买入日2025-01-21：")
print("  - 前一交易日2025-01-20：MA5=11.46, MA10=11.42, MA5>MA10=True")
print("  - 再前一交易日2025-01-17：MA5=11.42, MA10=11.42, MA5≈MA10")
print("  - 结论：2025-01-17时MA5≈MA10，2025-01-20时MA5>MA10，金叉确认")

print("\n聚宽买入日2025-02-10：")
print("  - 前一交易日2025-02-07：MA5=11.38, MA10=11.35, MA5>MA10=True")
print("  - 再前一交易日2025-02-06：MA5=11.37, MA10=11.37, MA5≈MA10")
print("  - 结论：2025-02-06时MA5≈MA10，2025-02-07时MA5>MA10，金叉确认")

print("\n【聚宽信号逻辑】")
print("信号在T日生成，使用T-1日的MA数据")
print("金叉条件：T-2时MA5<=MA10 且 T-1时MA5>MA10")
print("死叉条件：T-2时MA5>=MA10 且 T-1时MA5<MA10")
print("交易执行：T+1日开盘")

print("\n【验证】")
for i in range(2, len(dates)):
    t_date = dates[i]
    t1_date = dates[i-1]
    t2_date = dates[i-2]
    
    if np.isnan(ma5[i-1]) or np.isnan(ma10[i-1]) or np.isnan(ma5[i-2]) or np.isnan(ma10[i-2]):
        continue
    
    signal = None
    if ma5[i-2] <= ma10[i-2] and ma5[i-1] > ma10[i-1]:
        signal = "金叉→买入"
    elif ma5[i-2] >= ma10[i-2] and ma5[i-1] < ma10[i-1]:
        signal = "死叉→卖出"
    
    if signal:
        print(f"  {t_date}: {signal} (基于{t1_date}和{t2_date}的MA)")
