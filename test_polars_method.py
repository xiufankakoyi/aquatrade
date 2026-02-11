"""
测试 _read_stock_limit_status_polars 方法
"""
import time
import sys
sys.path.insert(0, r'd:\aquatrade')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

query = OptimizedStockDataQuery()

start_str, end_str = '2024-04-01', '2024-05-25'

print("测试 _read_stock_limit_status_polars...")
t0 = time.perf_counter()
limit_pl = query._read_stock_limit_status_polars(start_date=start_str, end_date=end_str)
t1 = time.perf_counter()
print(f"Polars 方法耗时: {t1 - t0:.4f}s, 行数: {len(limit_pl)}")

print("\n测试 to_pandas 转换...")
t0 = time.perf_counter()
limit_df = limit_pl.to_pandas()
t1 = time.perf_counter()
print(f"to_pandas 耗时: {t1 - t0:.4f}s")

print("\n测试 _read_stock_limit_status_parquet (旧方法)...")
t0 = time.perf_counter()
limit_df_old = query._read_stock_limit_status_parquet(start_date=start_str, end_date=end_str)
t1 = time.perf_counter()
print(f"旧方法耗时: {t1 - t0:.4f}s, 行数: {len(limit_df_old)}")
