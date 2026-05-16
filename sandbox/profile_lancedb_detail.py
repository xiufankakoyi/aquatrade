"""
深入分析 LanceDB 读取耗时 - 修复版
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import lancedb
import polars as pl
import numpy as np


def profile_lancedb_read():
    """分析 LanceDB 读取各环节"""
    print("=" * 60)
    print("LanceDB 读取耗时分析")
    print("=" * 60)
    
    db_path = Path(__file__).parent.parent / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    start_date = "2026-01-01"
    end_date = "2026-03-13"
    fields = ['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
    
    table = db.open_table("daily_ohlcv")
    
    # 环节1: to_arrow 全量读取
    t0 = time.perf_counter()
    arrow_table = table.to_arrow()
    to_arrow_time = time.perf_counter() - t0
    print(f"[1] to_arrow 全量读取: {to_arrow_time*1000:.1f}ms, {len(arrow_table)} 行")
    
    # 环节2: Polars 转换
    t0 = time.perf_counter()
    df = pl.from_arrow(arrow_table)
    polars_time = time.perf_counter() - t0
    print(f"[2] Polars 转换: {polars_time*1000:.1f}ms")
    
    # 环节3: 日期过滤
    t0 = time.perf_counter()
    df = df.filter(
        (pl.col('trade_date') >= pl.lit(start_date).str.to_date()) & 
        (pl.col('trade_date') <= pl.lit(end_date).str.to_date())
    )
    filter_time = time.perf_counter() - t0
    print(f"[3] 日期过滤: {filter_time*1000:.1f}ms, 剩余 {len(df)} 行")
    
    # 环节4: 排序
    t0 = time.perf_counter()
    df = df.sort(['stock_code', 'trade_date'])
    sort_time = time.perf_counter() - t0
    print(f"[4] 排序: {sort_time*1000:.1f}ms")
    
    # 环节5: partition_by 分组
    t0 = time.perf_counter()
    partitions = df.partition_by('stock_code', as_dict=True)
    partition_time = time.perf_counter() - t0
    print(f"[5] partition_by 分组: {partition_time*1000:.1f}ms, {len(partitions)} 组")
    
    # 环节6: to_numpy 转换
    t0 = time.perf_counter()
    result = {}
    for code_key, group in partitions.items():
        code = code_key[0] if isinstance(code_key, tuple) else code_key
        result[code] = {}
        for col in group.columns:
            if col == 'stock_code':
                continue
            result[code][col] = group[col].to_numpy()
    numpy_time = time.perf_counter() - t0
    print(f"[6] to_numpy 转换: {numpy_time*1000:.1f}ms")
    
    total = to_arrow_time + polars_time + filter_time + sort_time + partition_time + numpy_time
    print(f"\n总计: {total*1000:.1f}ms")
    
    print("\n" + "=" * 60)
    print("耗时占比")
    print("=" * 60)
    print(f"to_arrow 全量: {to_arrow_time/total*100:.1f}% ⚠️ 主要耗时")
    print(f"Polars 转换: {polars_time/total*100:.1f}%")
    print(f"日期过滤: {filter_time/total*100:.1f}%")
    print(f"排序: {sort_time/total*100:.1f}%")
    print(f"partition_by: {partition_time/total*100:.1f}%")
    print(f"to_numpy: {numpy_time/total*100:.1f}%")


if __name__ == "__main__":
    profile_lancedb_read()
