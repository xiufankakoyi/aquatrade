"""
性能分析：找出查询慢的真正原因
"""
import time
import sys
sys.path.insert(0, r'd:\aquatrade')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("创建查询实例...")
query = OptimizedStockDataQuery()

print(f"\n后端状态:")
print(f"  使用 Polars: True")
print(f"  使用 ArcticDB: {query._use_arcticdb if hasattr(query, '_use_arcticdb') else 'N/A'}")

start_str, end_str = '2024-04-01', '2024-05-25'

print(f"\n测试查询: {start_str} 到 {end_str}")
print("="*60)

t0 = time.perf_counter()
result = query.get_all_daily_data_for_period(start_str, end_str)
t1 = time.perf_counter()

print(f"\n总耗时: {t1 - t0:.2f}s")
print(f"返回行数: {len(result)}")
print(f"列数: {len(result.columns)}")
