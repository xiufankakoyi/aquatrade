import os
import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
import polars as pl

print("=" * 70)
print("ArcticDB 数据库概览")
print("=" * 70)

# 检查所有库
libraries = ['stock_daily', 'benchmark_daily', 'stock_basic', 'stock_info', 'factor', 'limit_status']

for lib_name in libraries:
    try:
        arctic = get_arctic_instance_for_library(lib_name)
        existing_libs = arctic.list_libraries()
        
        if lib_name in existing_libs:
            lib = arctic[lib_name]
            symbols = lib.list_symbols()
            
            print(f"\n【{lib_name}】")
            print(f"  symbol 数量: {len(symbols)}")
            
            if symbols:
                # 获取日期范围
                min_dates = []
                max_dates = []
                
                for sym in symbols[:20]:  # 检查前20个
                    try:
                        data = lib.read(sym)
                        df = data.data
                        if hasattr(df, 'index') and len(df) > 0:
                            min_dates.append(df.index.min())
                            max_dates.append(df.index.max())
                    except:
                        pass
                
                if min_dates:
                    print(f"  日期范围: {min(min_dates).strftime('%Y-%m-%d')} ~ {max(max_dates).strftime('%Y-%m-%d')}")
                
                # 显示前5个 symbol
                print(f"  示例 symbol: {symbols[:5]}")
        else:
            print(f"\n【{lib_name}】库不存在")
    except Exception as e:
        print(f"\n【{lib_name}】错误: {e}")

# 检查 Parquet 文件
print("\n" + "=" * 70)
print("Parquet 文件概览")
print("=" * 70)

parquet_dir = 'C:/Users/Liu/Desktop/projects/aquatrade/data/parquet_data'
if os.path.exists(parquet_dir):
    for f in os.listdir(parquet_dir):
        if f.endswith('.parquet'):
            fpath = os.path.join(parquet_dir, f)
            try:
                df = pl.scan_parquet(fpath)
                cols = df.collect_schema().names()
                
                # 检查日期列
                date_cols = [c for c in cols if 'date' in c.lower() or 'trade_date' in c.lower()]
                if date_cols:
                    dates = df.select(date_cols[0]).unique().collect().to_series().to_list()
                    if dates:
                        dates_sorted = sorted([str(d) for d in dates])
                        print(f"\n【{f}】")
                        print(f"  行数: {df.select(pl.len()).collect().item()}")
                        print(f"  日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]}")
                        print(f"  列数: {len(cols)}")
                else:
                    print(f"\n【{f}】")
                    print(f"  行数: {df.select(pl.len()).collect().item()}")
                    print(f"  列数: {len(cols)}")
            except Exception as e:
                print(f"\n【{f}】读取失败: {e}")
