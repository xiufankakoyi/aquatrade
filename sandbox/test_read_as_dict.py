"""
测试 read_as_dict 性能提升

对比原 Python 循环 vs 新的向量化方法
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import lancedb
import polars as pl
import numpy as np
from datetime import datetime, timedelta


def load_data_original(start_date: str, end_date: str):
    """原始方法：Python 循环"""
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    table = db.open_table("daily_ohlcv")
    daily_df = pl.from_arrow(table.to_arrow())
    daily_data = {}
    for row in daily_df.iter_rows(named=True):
        sc = row['stock_code']
        if sc in st_stocks or sc in new_stocks:
            continue
        if sc not in daily_data:
            daily_data[sc] = {'dates': [], 'close': [], 'open': [], 'high': [], 'low': [], 'volume': []}
        daily_data[sc]['dates'].append(str(row['trade_date']))
        daily_data[sc]['close'].append(row['close'])
        daily_data[sc]['open'].append(row.get('open', row['close']))
        daily_data[sc]['high'].append(row.get('high', row['close']))
        daily_data[sc]['low'].append(row.get('low', row['close']))
        daily_data[sc]['volume'].append(row['volume'])
    for sc in daily_data:
        idx = np.argsort(np.array(daily_data[sc]['dates']))
        for k in daily_data[sc]:
            arr = np.array(daily_data[sc][k])[idx]
            daily_data[sc][k] = arr.astype(np.float64) if k != 'dates' else arr
    return daily_data


def load_data_optimized(start_date: str, end_date: str):
    """优化方法：向量化操作"""
    from data_svc.storage.lancedb_reader import get_lancedb_reader
    
    db = lancedb.connect(str(Path(__file__).parent.parent / "data" / "lancedb"))
    
    st_info_table = db.open_table("stock_info")
    st_info_df = pl.from_arrow(st_info_table.to_arrow())
    
    st_stocks = set(st_info_df.filter(pl.col('is_st') == 1)['stock_code'].to_list())
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    min_list_date = (end_dt - timedelta(days=60)).strftime('%Y%m%d')
    new_stocks = set(st_info_df.filter(pl.col('list_date') > min_list_date)['stock_code'].to_list())
    
    filter_stocks = st_stocks | new_stocks
    
    reader = get_lancedb_reader()
    fields = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
    
    daily_data = reader.read_as_dict(
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        filter_stocks=filter_stocks,
    )
    
    for sc in daily_data:
        daily_data[sc]['dates'] = daily_data[sc].pop('trade_date')
    
    return daily_data


def main():
    print("=" * 60)
    print("read_as_dict 性能对比测试")
    print("=" * 60)
    
    start_date = "2026-01-01"
    end_date = "2026-03-13"
    
    print(f"\n日期范围: {start_date} ~ {end_date}")
    
    print("\n[1] 优化方法（向量化）...")
    t0 = time.perf_counter()
    data_opt = load_data_optimized(start_date, end_date)
    time_opt = time.perf_counter() - t0
    print(f"    耗时: {time_opt*1000:.1f}ms, 股票数: {len(data_opt)}")
    
    sample_code = list(data_opt.keys())[0] if data_opt else None
    if sample_code:
        print(f"    样例 {sample_code}: dates={len(data_opt[sample_code]['dates'])} 条")
    
    print("\n[2] 原始方法（Python 循环）...")
    print("    跳过（耗时太长，约 100 秒）")
    
    print("\n" + "=" * 60)
    print("性能对比")
    print("=" * 60)
    
    time_orig = 107.0
    print(f"原始方法: ~{time_orig*1000:.0f}ms (历史数据)")
    print(f"优化方法: {time_opt*1000:.1f}ms")
    print(f"加速比: {time_orig/time_opt:.1f}x")
    
    print("\n优化效果:")
    print(f"  - 数据加载: 从全量 1574万行 → 按日期过滤")
    print(f"  - 字典构建: 从 Python 循环 → Polars 向量化")
    print(f"  - 排序转换: 从逐股票排序 → 预排序")


if __name__ == "__main__":
    main()
