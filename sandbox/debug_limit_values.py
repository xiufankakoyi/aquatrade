"""
检查 limit_up 和 limit_down 列的值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager

# 创建数据管理器
data_manager = UnifiedDataManager()

# 读取数据
df = data_manager.read('stock_daily', start_date='2024-01-02', end_date='2024-01-10')

# 检查 limit_up 列
print("limit_up 列:")
print(f"  类型: {df['limit_up'].dtype}")
print(f"  最小值: {df['limit_up'].min()}")
print(f"  最大值: {df['limit_up'].max()}")
print(f"  平均值: {df['limit_up'].mean()}")
print(f"  前10个值:")
for row in df.head(10).iter_rows(named=True):
    print(f"    {row['stock_code']} @ {row['trade_date']}: limit_up={row['limit_up']}, close={row['close']}")

# 检查 limit_down 列
print("\nlimit_down 列:")
print(f"  类型: {df['limit_down'].dtype}")
print(f"  最小值: {df['limit_down'].min()}")
print(f"  最大值: {df['limit_down'].max()}")
print(f"  平均值: {df['limit_down'].mean()}")

# 计算是否涨停
df_with_limit = df.with_columns([
    (pl.col('close') >= pl.col('limit_up')).alias('is_limit_up_calc'),
    (pl.col('close') <= pl.col('limit_down')).alias('is_limit_down_calc')
])

print("\n计算得到的涨停状态:")
print(f"  is_limit_up_calc True: {df_with_limit['is_limit_up_calc'].sum()}")
print(f"  is_limit_down_calc True: {df_with_limit['is_limit_down_calc'].sum()}")
