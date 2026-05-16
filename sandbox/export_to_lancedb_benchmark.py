#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出 ArcticDB 数据到 LanceDB 并进行性能对比测试
"""
import sys
from pathlib import Path
import time
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import pyarrow as pa
from arcticdb import Arctic
import lancedb

ARCTIC_BASE = Path("C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db")
LANCE_PATH = Path("C:/Users/Liu/Desktop/projects/aquatrade/data/lance_db")

START_DATE = "2024-01-01"
END_DATE = "2026-12-31"


def check_arcticdb_data():
    """检查 ArcticDB 数据结构"""
    print("=" * 70)
    print("检查 ArcticDB 数据结构")
    print("=" * 70)
    
    results = {}
    
    for lib_name in ["stock_daily", "factor", "benchmark"]:
        lib_path = ARCTIC_BASE / lib_name
        if not lib_path.exists():
            print(f"\n{lib_name}: 目录不存在")
            continue
            
        print(f"\n【{lib_name}】")
        arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
        libs = arctic.list_libraries()
        
        if lib_name not in libs:
            print(f"  库不存在")
            continue
            
        lib = arctic[lib_name]
        symbols = list(lib.list_symbols())
        print(f"  Symbol 数量: {len(symbols)}")
        
        if symbols:
            sample_sym = symbols[0]
            data = lib.read(sample_sym)
            df = pl.from_pandas(data.data) if hasattr(data.data, 'to_pandas') else data.data
            print(f"  样例 {sample_sym}: {len(df)} 行")
            print(f"  列: {df.columns[:8].to_list()}")
            
            if 'trade_date' in df.columns:
                min_date = str(df['trade_date'].min())
                max_date = str(df['trade_date'].max())
                print(f"  日期范围: {min_date} ~ {max_date}")
                results[lib_name] = {
                    'symbols': len(symbols),
                    'sample_rows': len(df),
                    'columns': df.columns.to_list(),
                    'min_date': min_date,
                    'max_date': max_date
                }
    
    return results


def export_to_lancedb():
    """导出数据到 LanceDB"""
    print("\n" + "=" * 70)
    print("导出数据到 LanceDB")
    print("=" * 70)
    
    LANCE_PATH.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(LANCE_PATH))
    
    total_start = time.time()
    
    for lib_name in ["stock_daily", "factor", "benchmark"]:
        lib_path = ARCTIC_BASE / lib_name
        if not lib_path.exists():
            print(f"\n{lib_name}: 跳过（目录不存在）")
            continue
        
        print(f"\n【导出 {lib_name}】")
        start = time.time()
        
        arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
        libs = arctic.list_libraries()
        
        if lib_name not in libs:
            print(f"  库不存在，跳过")
            continue
        
        lib = arctic[lib_name]
        symbols = list(lib.list_symbols())
        
        all_dfs = []
        for i, sym in enumerate(symbols):
            try:
                data = lib.read(sym)
                pdf = data.data
                
                if isinstance(pdf, pl.DataFrame):
                    df = pdf
                else:
                    df = pl.from_pandas(pdf)
                
                if 'trade_date' in df.columns:
                    df = df.filter(
                        (pl.col('trade_date') >= START_DATE) & 
                        (pl.col('trade_date') <= END_DATE)
                    )
                
                if len(df) > 0:
                    df = df.with_columns(pl.lit(sym).alias('symbol'))
                    all_dfs.append(df)
                    
                if (i + 1) % 500 == 0:
                    print(f"  已处理 {i + 1}/{len(symbols)} symbols...")
                    
            except Exception as e:
                if i < 5:
                    print(f"  读取 {sym} 失败: {e}")
        
        if all_dfs:
            combined = pl.concat(all_dfs)
            print(f"  合并后: {len(combined)} 行")
            
            table = combined.to_arrow()
            
            if lib_name in db.table_names():
                db.drop_table(lib_name)
            
            db.create_table(lib_name, table)
            print(f"  写入 LanceDB 完成")
        
        elapsed = time.time() - start
        print(f"  耗时: {elapsed:.2f}s")
    
    total_elapsed = time.time() - total_start
    print(f"\n总导出耗时: {total_elapsed:.2f}s")
    
    return db


def benchmark_query(db):
    """性能对比测试"""
    print("\n" + "=" * 70)
    print("性能对比测试")
    print("=" * 70)
    
    test_dates = ["2024-06-01", "2025-01-15", "2025-06-20"]
    test_stocks = ["000001.SZ", "600000.SH", "000002.SZ"]
    
    results = {
        'arcticdb': {'single': [], 'batch': [], 'filter': []},
        'lancedb': {'single': [], 'batch': [], 'filter': []}
    }
    
    for lib_name in ["stock_daily", "factor"]:
        lib_path = ARCTIC_BASE / lib_name
        if not lib_path.exists():
            continue
            
        print(f"\n【{lib_name}】")
        
        arctic = Arctic(f"lmdb://{lib_path}?map_size=10GB")
        arctic_lib = arctic[lib_name]
        
        if lib_name not in db.table_names():
            print(f"  LanceDB 表不存在，跳过")
            continue
        
        lance_table = db.open_table(lib_name)
        
        symbols = list(arctic_lib.list_symbols())
        if not symbols:
            continue
        
        test_sym = symbols[0]
        
        print("\n1. 单条查询测试 (读取单只股票全部数据)")
        
        times = []
        for _ in range(5):
            start = time.time()
            data = arctic_lib.read(test_sym)
            df = pl.from_pandas(data.data)
            times.append(time.time() - start)
        arctic_single = sum(times) / len(times)
        results['arcticdb']['single'].append(arctic_single)
        print(f"  ArcticDB: {arctic_single*1000:.2f}ms (avg of 5)")
        
        times = []
        for _ in range(5):
            start = time.time()
            df = lance_table.search().where(f"symbol = '{test_sym}'").to_polars()
            times.append(time.time() - start)
        lance_single = sum(times) / len(times)
        results['lancedb']['single'].append(lance_single)
        print(f"  LanceDB:  {lance_single*1000:.2f}ms (avg of 5)")
        
        print("\n2. 日期范围过滤查询")
        
        times = []
        for _ in range(5):
            start = time.time()
            data = arctic_lib.read(test_sym, date_range=(START_DATE, END_DATE))
            df = pl.from_pandas(data.data)
            times.append(time.time() - start)
        arctic_filter = sum(times) / len(times)
        results['arcticdb']['filter'].append(arctic_filter)
        print(f"  ArcticDB: {arctic_filter*1000:.2f}ms (avg of 5)")
        
        times = []
        for _ in range(5):
            start = time.time()
            df = lance_table.search() \
                .where(f"symbol = '{test_sym}'") \
                .where(f"trade_date >= '{START_DATE}'") \
                .where(f"trade_date <= '{END_DATE}'") \
                .to_polars()
            times.append(time.time() - start)
        lance_filter = sum(times) / len(times)
        results['lancedb']['filter'].append(lance_filter)
        print(f"  LanceDB:  {lance_filter*1000:.2f}ms (avg of 5)")
        
        print("\n3. 批量查询测试 (读取所有股票某日数据)")
        
        times = []
        for _ in range(5):
            start = time.time()
            all_dfs = []
            for sym in symbols[:100]:
                try:
                    data = arctic_lib.read(sym)
                    df = pl.from_pandas(data.data)
                    if 'trade_date' in df.columns:
                        df = df.filter(pl.col('trade_date') == test_dates[0])
                    if len(df) > 0:
                        all_dfs.append(df)
                except:
                    pass
            if all_dfs:
                combined = pl.concat(all_dfs)
            times.append(time.time() - start)
        arctic_batch = sum(times) / len(times)
        results['arcticdb']['batch'].append(arctic_batch)
        print(f"  ArcticDB (100 stocks): {arctic_batch*1000:.2f}ms (avg of 5)")
        
        times = []
        for _ in range(5):
            start = time.time()
            df = lance_table.search() \
                .where(f"trade_date = '{test_dates[0]}'") \
                .limit(10000) \
                .to_polars()
            times.append(time.time() - start)
        lance_batch = sum(times) / len(times)
        results['lancedb']['batch'].append(lance_batch)
        print(f"  LanceDB:  {lance_batch*1000:.2f}ms (avg of 5)")
    
    return results


def print_summary(results):
    """打印性能对比总结"""
    print("\n" + "=" * 70)
    print("性能对比总结")
    print("=" * 70)
    
    print("\n| 测试项 | ArcticDB | LanceDB | 差异 |")
    print("|--------|----------|---------|------|")
    
    for test_type in ['single', 'filter', 'batch']:
        arctic_avg = sum(results['arcticdb'][test_type]) / len(results['arcticdb'][test_type]) if results['arcticdb'][test_type] else 0
        lance_avg = sum(results['lancedb'][test_type]) / len(results['lancedb'][test_type]) if results['lancedb'][test_type] else 0
        
        if arctic_avg > 0:
            diff = ((lance_avg - arctic_avg) / arctic_avg) * 100
            diff_str = f"{diff:+.1f}%"
        else:
            diff_str = "N/A"
        
        print(f"| {test_type:8} | {arctic_avg*1000:6.2f}ms | {lance_avg*1000:6.2f}ms | {diff_str:6} |")


def main():
    print("ArcticDB vs LanceDB 性能对比测试")
    print(f"数据范围: {START_DATE} ~ {END_DATE}")
    
    check_arcticdb_data()
    db = export_to_lancedb()
    results = benchmark_query(db)
    print_summary(results)
    
    print("\n测试完成!")


if __name__ == "__main__":
    main()
