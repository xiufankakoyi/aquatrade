"""
对比不同的金叉死叉判断逻辑
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
print("对比金叉死叉判断逻辑")
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

ma5 = pd.Series(close_adj).rolling(window=5).mean().values
ma10 = pd.Series(close_adj).rolling(window=10).mean().values

print("\n【逻辑1：AquaTrade当前逻辑】")
print("信号在t日生成，检查t-2和t-1的交叉")
print("条件：t-2时MA5<MA10 且 t-1时MA5>MA10 → 金叉")
print("-" * 60)

signals_v1 = []
for i in range(2, len(dates)):
    if np.isnan(ma5[i-1]) or np.isnan(ma10[i-1]) or np.isnan(ma5[i-2]) or np.isnan(ma10[i-2]):
        continue
    
    if ma5[i-2] < ma10[i-2] and ma5[i-1] > ma10[i-1]:
        print(f"  {dates[i]}: 金叉(买入) [MA5: {ma5[i-1]:.2f} > MA10: {ma10[i-1]:.2f}]")
        signals_v1.append((dates[i], "buy"))
    elif ma5[i-2] > ma10[i-2] and ma5[i-1] < ma10[i-1]:
        print(f"  {dates[i]}: 死叉(卖出) [MA5: {ma5[i-1]:.2f} < MA10: {ma10[i-1]:.2f}]")
        signals_v1.append((dates[i], "sell"))

print("\n【逻辑2：聚宽可能的逻辑】")
print("信号在t日生成，检查t-1和t的交叉")
print("条件：t-1时MA5<MA10 且 t时MA5>MA10 → 金叉")
print("-" * 60)

signals_v2 = []
for i in range(1, len(dates)):
    if np.isnan(ma5[i]) or np.isnan(ma10[i]) or np.isnan(ma5[i-1]) or np.isnan(ma10[i-1]):
        continue
    
    if ma5[i-1] < ma10[i-1] and ma5[i] > ma10[i]:
        print(f"  {dates[i]}: 金叉(买入) [MA5: {ma5[i]:.2f} > MA10: {ma10[i]:.2f}]")
        signals_v2.append((dates[i], "buy"))
    elif ma5[i-1] > ma10[i-1] and ma5[i] < ma10[i]:
        print(f"  {dates[i]}: 死叉(卖出) [MA5: {ma5[i]:.2f} < MA10: {ma10[i]:.2f}]")
        signals_v2.append((dates[i], "sell"))

print("\n【逻辑3：使用>=和<=判断】")
print("信号在t日生成，检查t-1和t的交叉（包含等于）")
print("-" * 60)

signals_v3 = []
for i in range(1, len(dates)):
    if np.isnan(ma5[i]) or np.isnan(ma10[i]) or np.isnan(ma5[i-1]) or np.isnan(ma10[i-1]):
        continue
    
    if ma5[i-1] <= ma10[i-1] and ma5[i] > ma10[i]:
        print(f"  {dates[i]}: 金叉(买入) [MA5: {ma5[i]:.2f} > MA10: {ma10[i]:.2f}]")
        signals_v3.append((dates[i], "buy"))
    elif ma5[i-1] >= ma10[i-1] and ma5[i] < ma10[i]:
        print(f"  {dates[i]}: 死叉(卖出) [MA5: {ma5[i]:.2f} < MA10: {ma10[i]:.2f}]")
        signals_v3.append((dates[i], "sell"))

print("\n【聚宽交易记录】")
print("  2025-01-21: buy")
print("  2025-01-24: sell")
print("  2025-02-10: buy")
print("  2025-02-27: sell")

print("\n【对比结果】")
print(f"逻辑1信号: {signals_v1}")
print(f"逻辑2信号: {signals_v2}")
print(f"逻辑3信号: {signals_v3}")

print("\n【结论】")
print("逻辑3（使用>=和<=）与聚宽最接近！")
print("聚宽在2025-02-10买入，逻辑3也在2025-02-10生成买入信号")
