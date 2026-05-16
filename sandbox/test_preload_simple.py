"""
简单预加载测试
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import get_unified_manager

print("=" * 70)
print("简单预加载测试")
print("=" * 70)

manager = get_unified_manager()

print(f"\n缓存状态: cache_loaded={manager._cache_loaded}")
print(f"缓存范围: {manager._preloaded_date_range}")

# 直接读取数据
print("\n[1] 直接读取数据...")
df = manager.read('stock_daily', start_date='2025-01-01', end_date='2025-01-31')
print(f"   数据形状: {df.shape}")

if not df.is_empty():
    print(f"   列名: {df.columns}")
    print(f"\n   前3行:")
    print(df.head(3))

print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)
