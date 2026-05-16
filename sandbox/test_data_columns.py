"""
检查原始数据的列名
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import get_unified_manager

manager = get_unified_manager()

# 从 ArcticDB 读取数据
df = manager.read('stock_daily', start_date='2025-01-01', end_date='2025-01-31')

print("数据列名:")
print(df.columns)
print(f"\n数据行数: {len(df)}")

# 查看前几行
print("\n前5行数据:")
print(df.head())

# 检查是否有 limit_up/limit_down
if 'limit_up' in df.columns:
    print("\n✓ 有 limit_up 列")
else:
    print("\n✗ 没有 limit_up 列")

if 'limit_down' in df.columns:
    print("✓ 有 limit_down 列")
else:
    print("✗ 没有 limit_down 列")
