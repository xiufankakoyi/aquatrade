"""
调试状态字段计算
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager

# 创建数据管理器
data_manager = UnifiedDataManager()

print("=" * 80)
print("调试状态字段计算")
print("=" * 80)

# 获取数据
start_date = '2024-01-02'
end_date = '2024-01-10'

stock_daily = data_manager.read('stock_daily', start_date=start_date, end_date=end_date)

print(f"\n原始数据列: {stock_daily.columns}")
print(f"数据行数: {len(stock_daily)}")

# 检查 limit_up 和 limit_down 字段
if 'limit_up' in stock_daily.columns:
    print(f"\nlimit_up 字段:")
    print(f"  唯一值数量: {stock_daily['limit_up'].n_unique()}")
    print(f"  最小值: {stock_daily['limit_up'].min()}")
    print(f"  最大值: {stock_daily['limit_up'].max()}")

if 'limit_down' in stock_daily.columns:
    print(f"\nlimit_down 字段:")
    print(f"  唯一值数量: {stock_daily['limit_down'].n_unique()}")
    print(f"  最小值: {stock_daily['limit_down'].min()}")
    print(f"  最大值: {stock_daily['limit_down'].max()}")

# 计算 is_limit_up
df_enhanced = stock_daily.with_columns([
    (pl.col('close') >= pl.col('limit_up')).cast(pl.Float64).alias('is_limit_up')
])

print(f"\n计算后的 is_limit_up 字段:")
print(f"  唯一值: {df_enhanced['is_limit_up'].unique().to_list()}")
print(f"  True (1.0): {(df_enhanced['is_limit_up'] == 1.0).sum()}")
print(f"  False (0.0): {(df_enhanced['is_limit_up'] == 0.0).sum()}")

# 检查某一天的数据
date_str = '2024-01-03'
df_day = df_enhanced.filter(pl.col('trade_date') == date_str)

print(f"\n{date_str} 的数据:")
print(f"  总行数: {len(df_day)}")
print(f"  is_limit_up == 1.0: {(df_day['is_limit_up'] == 1.0).sum()}")
print(f"  is_limit_up == 0.0: {(df_day['is_limit_up'] == 0.0).sum()}")

# 显示一些 is_limit_up == 1.0 的股票
limit_up_stocks = df_day.filter(pl.col('is_limit_up') == 1.0).select(['stock_code', 'close', 'limit_up', 'is_limit_up'])
print(f"\n涨停股票示例:")
print(limit_up_stocks.head(10).to_pandas())
