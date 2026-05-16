"""
诊断 Parquet 和 ArcticDB 数据类型差异
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

print("=" * 80)
print("诊断数据类型差异")
print("=" * 80)

parquet_path = Path("./data/parquet_data/stock_daily.parquet")

print("\n1. Parquet 文件 Schema (PyArrow):")
parquet_file = pq.ParquetFile(parquet_path)
parquet_schema = parquet_file.schema_arrow
print(parquet_schema)

print("\n2. Polars 读取后的 Schema:")
df_pl = pl.read_parquet(parquet_path, n_rows=5)
print(df_pl.schema)

print("\n3. Polars → Arrow Table Schema:")
arrow_table = df_pl.to_arrow()
print(arrow_table.schema)

print("\n4. 关键列类型对比:")
key_columns = ['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10']

print(f"\n{'列名':<20} {'Parquet':<20} {'Polars':<20} {'Arrow':<20}")
print("-" * 80)

for col in key_columns:
    if col in parquet_schema.names:
        parquet_type = parquet_schema.field(col).type
    else:
        parquet_type = "N/A"
    
    if col in df_pl.columns:
        polars_type = df_pl[col].dtype
    else:
        polars_type = "N/A"
    
    if col in arrow_table.schema.names:
        arrow_type = arrow_table.schema.field(col).type
    else:
        arrow_type = "N/A"
    
    print(f"{col:<20} {str(parquet_type):<20} {str(polars_type):<20} {str(arrow_type):<20}")

print("\n5. 检查 ArcticDB 已有数据:")
try:
    import arcticdb as adb
    
    arctic = adb.Arctic("lmdb://./data/arctic_db")
    
    if 'stock_daily' in arctic.list_libraries():
        lib = arctic['stock_daily']
        symbols = lib.list_symbols()
        
        print(f"\nArcticDB stock_daily 符号数: {len(symbols)}")
        
        if symbols:
            first_sym = symbols[0]
            result = lib.read(first_sym)
            data = result.data
            
            print(f"\n符号 '{first_sym}' 数据类型: {type(data)}")
            
            if isinstance(data, pa.Table):
                print(f"Arrow Table schema:")
                print(data.schema)
            else:
                print(f"Pandas DataFrame dtypes:")
                print(data.dtypes)
    else:
        print("\nArcticDB stock_daily 库不存在")
        
except Exception as e:
    print(f"\nArcticDB 检查失败: {e}")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("""
类型转换链：
1. Parquet → PyArrow: 保持原始类型
2. PyArrow → Polars: 可能发生类型推断
3. Polars → Arrow Table: 使用 Polars 的类型系统
4. Arrow Table → ArcticDB: 应该保持 Arrow 类型

问题可能出在：
- Polars 读取 Parquet 时的类型推断
- ArcticDB 内部存储时的类型规范化
""")
