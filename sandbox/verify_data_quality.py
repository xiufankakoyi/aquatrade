"""
三层数据验证脚本
第一层：宏观比对
第二层：微观核对
第三层：业务语义验证
"""
from pathlib import Path
from arcticdb import Arctic
import pandas as pd
import numpy as np

base_path = Path('data/arctic_db')
stock_daily_path = base_path / 'stock_daily'
daily_path = base_path / 'daily'

arctic_stock = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')
arctic_daily = Arctic(f'lmdb://{daily_path}?map_size=10GB')

stock_lib = arctic_stock['stock_daily']
daily_lib = arctic_daily['daily']

stock_symbols = set(stock_lib.list_symbols())
daily_symbols = set(daily_lib.list_symbols())

# 过滤掉 'stock_daily' 这个错误的 symbol
if 'stock_daily' in stock_symbols:
    stock_symbols.remove('stock_daily')
if 'stock_daily' in daily_symbols:
    daily_symbols.remove('stock_daily')

common_symbols = list(stock_symbols & daily_symbols)

print("=" * 70)
print("第一层：宏观比对")
print("=" * 70)

# 1.1 总行数比对
total_stock = 0
total_daily = 0

# 抽样100只股票
sample_symbols = common_symbols[:100]
for s in sample_symbols:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    total_stock += len(df_stock)
    total_daily += len(df_daily)

print(f"抽样100只股票总行数:")
print(f"  stock_daily: {total_stock}")
print(f"  daily:       {total_daily}")
print(f"  差异:         {total_stock - total_daily}")

# 1.2 关键字段校验和
print("\n关键字段校验和 (抽样10只):")
sample_check = common_symbols[:10]
for s in sample_check:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    
    # 检查 close 字段
    close_sum_stock = df_stock['close'].sum()
    close_sum_daily = df_daily['close'].sum()
    diff = abs(close_sum_stock - close_sum_daily)
    status = "✓" if diff < 0.01 else "✗"
    print(f"  {s} close_sum: stock={close_sum_stock:.2f}, daily={close_sum_daily:.2f}, diff={diff:.4f} {status}")

print("\n" + "=" * 70)
print("第二层：微观核对")
print("=" * 70)

# 2.1 NULL值检查
print("\n2.1 NULL值检查 (抽样10只):")
for s in common_symbols[:10]:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    
    null_stock = df_stock.isnull().sum().sum()
    null_daily = df_daily.isnull().sum().sum()
    status = "✓" if null_stock == null_daily else "✗"
    print(f"  {s}: stock_nulls={null_stock}, daily_nulls={null_daily} {status}")

# 2.2 逐行逐列比对
print("\n2.2 逐行逐列精确比对 (抽样5只):")
for s in common_symbols[:5]:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    
    # 对齐索引
    common_idx = df_stock.index.intersection(df_daily.index)
    df_stock_aligned = df_stock.loc[common_idx].sort_index()
    df_daily_aligned = df_daily.loc[common_idx].sort_index()
    
    diff_count = 0
    for col in df_stock.columns:
        if col in df_daily_aligned:
            # 处理数值列
            if df_stock_aligned[col].dtype in ['float64', 'int64']:
                diff = ~np.isclose(df_stock_aligned[col].fillna(0), df_daily_aligned[col].fillna(0), rtol=1e-5)
                col_diff = diff.sum()
            else:
                col_diff = (df_stock_aligned[col] != df_daily_aligned[col]).sum()
            
            if col_diff > 0:
                diff_count += col_diff
                print(f"    {s}.{col}: 差异 {col_diff} 个")
    
    status = "✓" if diff_count == 0 else "✗"
    print(f"  {s}: 总差异数={diff_count} {status}")

print("\n" + "=" * 70)
print("第三层：业务语义验证")
print("=" * 70)

# 3.1 日期连续性检查
print("\n3.1 日期连续性检查 (抽样10只):")
for s in common_symbols[:10]:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    
    # 检查日期是否有缺失
    dates_stock = pd.to_datetime(df_stock.index).sort_values()
    dates_daily = pd.to_datetime(df_daily.index).sort_values()
    
    # 检查日期集合是否一致
    date_diff_stock = set(dates_stock.date) - set(dates_daily.date)
    date_diff_daily = set(dates_daily.date) - set(dates_stock.date)
    
    if date_diff_stock or date_diff_daily:
        print(f"  {s}: stock多{len(date_diff_stock)}个日期, daily多{len(date_diff_daily)}个日期 ✗")
    else:
        print(f"  {s}: 日期完全一致 ✓")

# 3.2 数值范围检查
print("\n3.2 数值范围检查 (close, volume, amount):")
for s in common_symbols[:5]:
    df_stock = stock_lib.read(s).data
    df_daily = daily_lib.read(s).data
    
    for col in ['close', 'volume', 'amount']:
        if col in df_stock.columns and col in df_daily.columns:
            stock_min, stock_max = df_stock[col].min(), df_stock[col].max()
            daily_min, daily_max = df_daily[col].min(), df_daily[col].max()
            
            range_match = (abs(stock_min - daily_min) < 0.01) and (abs(stock_max - daily_max) < 0.01)
            status = "✓" if range_match else "✗"
            print(f"  {s}.{col}: stock=[{stock_min:.2f}, {stock_max:.2f}], daily=[{daily_min:.2f}, {daily_max:.2f}] {status}")

# 3.3 数据类型检查
print("\n3.3 数据类型检查 (抽样1只):")
s = common_symbols[0]
df_stock = stock_lib.read(s).data
df_daily = daily_lib.read(s).data

for col in df_stock.columns:
    if col in df_daily.columns:
        type_stock = str(df_stock[col].dtype)
        type_daily = str(df_daily[col].dtype)
        status = "✓" if type_stock == type_daily else "✗"
        if type_stock != type_daily:
            print(f"  {col}: stock={type_stock}, daily={type_daily} {status}")

print("\n" + "=" * 70)
print("验证完成")
print("=" * 70)
