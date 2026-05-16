"""
检查数据存储状态
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

import polars as pl
from pathlib import Path

def check_parquet_data():
    """检查 Parquet 文件数据"""
    print("\n" + "=" * 80)
    print("检查 Parquet 文件数据")
    print("=" * 80)
    
    parquet_dir = Path("./data/parquet_data")
    
    files = {
        'stock_daily': parquet_dir / "stock_daily.parquet",
        'benchmark_daily': parquet_dir / "benchmark_daily.parquet",
        'limit_status': parquet_dir / "stock_limit_status.parquet",
    }
    
    for name, path in files.items():
        if path.exists():
            df = pl.scan_parquet(path)
            schema = df.collect_schema()
            
            date_col = 'trade_date' if 'trade_date' in schema.names() else 'date'
            
            if date_col in schema.names():
                result = df.select([
                    pl.col(date_col).min().alias('min_date'),
                    pl.col(date_col).max().alias('max_date'),
                    pl.len().alias('rows')
                ]).collect()
                
                print(f"\n{name}:")
                print(f"  文件: {path}")
                print(f"  行数: {result['rows'][0]:,}")
                print(f"  日期范围: {result['min_date'][0]} ~ {result['max_date'][0]}")
                print(f"  列: {schema.names()[:10]}...")
            else:
                print(f"\n{name}: 无日期列")
        else:
            print(f"\n{name}: 文件不存在")

def check_arcticdb_data():
    """检查 ArcticDB 数据"""
    print("\n" + "=" * 80)
    print("检查 ArcticDB 数据")
    print("=" * 80)
    
    try:
        import arcticdb as adb
        
        arctic = adb.Arctic("lmdb://./data/arctic_db")
        
        libraries = ['stock_daily', 'benchmark_daily', 'limit_status', 'factor']
        
        for lib_name in libraries:
            try:
                lib = arctic[lib_name]
                symbols = lib.list_symbols()
                
                print(f"\n{lib_name}:")
                print(f"  符号数: {len(symbols)}")
                
                if symbols:
                    total_rows = 0
                    for sym in symbols[:5]:
                        try:
                            result = lib.read(sym)
                            rows = len(result.data)
                            total_rows += rows
                            print(f"    - {sym}: {rows} 行")
                        except Exception as e:
                            print(f"    - {sym}: 读取失败 {e}")
                    
                    if len(symbols) > 5:
                        print(f"    ... 还有 {len(symbols) - 5} 个符号")
                    
                    print(f"  总行数(前5个): {total_rows}")
            except Exception as e:
                print(f"\n{lib_name}: 库不存在或读取失败 - {e}")
        
    except ImportError:
        print("ArcticDB 未安装")
    except Exception as e:
        print(f"ArcticDB 连接失败: {e}")

def check_data_consistency():
    """检查数据一致性"""
    print("\n" + "=" * 80)
    print("数据一致性检查")
    print("=" * 80)
    
    parquet_dir = Path("./data/parquet_data")
    stock_parquet = parquet_dir / "stock_daily.parquet"
    
    if stock_parquet.exists():
        df_parquet = pl.scan_parquet(stock_parquet)
        parquet_dates = df_parquet.select([
            pl.col('trade_date').min().alias('min'),
            pl.col('trade_date').max().alias('max'),
            pl.len().alias('rows')
        ]).collect()
        
        print(f"\nParquet stock_daily:")
        print(f"  行数: {parquet_dates['rows'][0]:,}")
        print(f"  日期: {parquet_dates['min'][0]} ~ {parquet_dates['max'][0]}")
    
    try:
        import arcticdb as adb
        arctic = adb.Arctic("lmdb://./data/arctic_db")
        
        lib = arctic['stock_daily']
        symbols = lib.list_symbols()
        
        if symbols:
            all_dates = set()
            total_rows = 0
            
            for sym in symbols:
                try:
                    result = lib.read(sym)
                    data = result.data
                    
                    import pyarrow as pa
                    if isinstance(data, pa.Table):
                        df = pl.from_arrow(data)
                    else:
                        df = pl.from_pandas(data)
                    
                    if 'trade_date' in df.columns:
                        dates = df['trade_date'].unique().to_list()
                        all_dates.update(str(d) for d in dates)
                    
                    total_rows += len(df)
                except Exception as e:
                    pass
            
            print(f"\nArcticDB stock_daily:")
            print(f"  符号数: {len(symbols)}")
            print(f"  总行数: {total_rows:,}")
            if all_dates:
                sorted_dates = sorted(all_dates)
                print(f"  日期: {sorted_dates[0]} ~ {sorted_dates[-1]}")
        else:
            print(f"\nArcticDB stock_daily: 无数据")
            
    except Exception as e:
        print(f"ArcticDB 检查失败: {e}")

if __name__ == "__main__":
    check_parquet_data()
    check_arcticdb_data()
    check_data_consistency()
    
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    print("""
如果 ArcticDB 数据不足，需要：
1. 运行数据迁移脚本，将 Parquet 数据导入 ArcticDB
2. 或运行 Tushare 更新脚本，直接写入 ArcticDB
""")
