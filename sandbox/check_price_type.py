"""
检查数据库中存储的是什么价格（前复权 vs 不复权）
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from pathlib import Path

print("=" * 70)
print("检查数据库中存储的价格类型")
print("=" * 70)

# 读取parquet文件
parquet_path = Path("data/parquet_data/stock_daily.parquet")
if not parquet_path.exists():
    parquet_path = Path("data/arctic_db/stock_daily.parquet")

if parquet_path.exists():
    print(f"\n读取: {parquet_path}")
    df = pl.scan_parquet(str(parquet_path)).filter(
        (pl.col('ts_code') == '000001.SZ') &
        (pl.col('trade_date') >= '2025-01-20') &
        (pl.col('trade_date') <= '2025-01-24')
    ).collect()
    
    print(f"\n【000001 2025-01-20 ~ 2025-01-24 数据】")
    print(df[['ts_code', 'trade_date', 'open', 'close', 'adj_factor']])
    
    print("\n【分析】")
    if 'adj_factor' in df.columns:
        adj_values = df['adj_factor'].unique()
        print(f"  复权因子值: {adj_values.to_list()}")
        if len(adj_values) == 1:
            print("  所有日期复权因子相同，说明这段时间没有除权除息")
        else:
            print("  复权因子不同，说明有除权除息事件")
    
    print("\n【问题】")
    print("  如果open/close是前复权价格，那回测时用这个价格交易是错误的！")
    print("  正确做法：")
    print("    1. 存储不复权价格 + 复权因子")
    print("    2. 交易时用不复权价格")
    print("    3. 指标计算时用动态前复权价格")
else:
    print(f"文件不存在: {parquet_path}")

# 检查ArcticDB中的数据
print("\n" + "=" * 70)
print("检查ArcticDB中的数据")
print("=" * 70)

try:
    from data_svc.storage.arcticdb_manager import ArcticDBManager
    import pandas as pd
    
    arctic = ArcticDBManager()
    
    # 列出库
    libs = arctic.arctic.list_libraries()
    print(f"\n库列表: {libs}")
    
    if 'stock_daily' in libs:
        lib = arctic.arctic['stock_daily']
        symbols = lib.list_symbols()
        print(f"stock_daily库中的symbols数量: {len(symbols)}")
        
        if 'stock_daily' in symbols:
            df = lib.read('stock_daily', as_of='2025-01-24').data
            if 'symbol' in df.columns:
                df_000001 = df[df['symbol'] == '000001']
            elif 'stock_code' in df.columns:
                df_000001 = df[df['stock_code'] == '000001']
            else:
                df_000001 = df.head(10)
            
            print(f"\n【000001数据样本】")
            print(df_000001.head(10))
            
            if 'adj_factor' in df_000001.columns:
                print(f"\n复权因子: {df_000001['adj_factor'].unique()}")
except Exception as e:
    print(f"ArcticDB检查失败: {e}")
    import traceback
    traceback.print_exc()
