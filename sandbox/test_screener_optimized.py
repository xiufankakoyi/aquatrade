#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试优化版 Stock Screener 性能

对比原版和优化版的性能差异
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import polars as pl
from datetime import datetime


def test_optimized_service():
    """测试优化版数据服务"""
    print("\n" + "="*80)
    print("测试优化版 ScreenerDataService")
    print("="*80)
    
    from server.routes.screener_data_service import get_screener_service
    
    service = get_screener_service()
    
    # 测试参数
    test_date = "2025-11-20"
    test_fields = ["close", "pe", "ma5", "ma10", "rsi_6", "macd_dif"]
    test_conditions = [
        {"field": "close", "operator": ">", "value": 10},
        {"field": "pe", "operator": "<", "value": 50},
    ]
    
    # 第一次查询（无缓存）
    print("\n【第一次查询 - 无缓存】")
    start = time.perf_counter()
    df1 = service.get_data(date=test_date, fields=test_fields, conditions=test_conditions)
    elapsed1 = (time.perf_counter() - start) * 1000
    
    if df1 is not None:
        print(f"  结果: {len(df1)} 行, {len(df1.columns)} 列")
        print(f"  耗时: {elapsed1:.2f}ms")
    else:
        print("  查询失败")
        return
    
    # 第二次查询（有缓存）
    print("\n【第二次查询 - 有缓存】")
    start = time.perf_counter()
    df2 = service.get_data(date=test_date, fields=test_fields, conditions=test_conditions)
    elapsed2 = (time.perf_counter() - start) * 1000
    
    if df2 is not None:
        print(f"  结果: {len(df2)} 行, {len(df2.columns)} 列")
        print(f"  耗时: {elapsed2:.2f}ms")
        print(f"  提速: {elapsed1/elapsed2:.1f}x")
    
    # 测试筛选
    print("\n【测试筛选条件】")
    start = time.perf_counter()
    df_filtered = service.apply_filter_optimized(df2, test_conditions, "AND")
    elapsed_filter = (time.perf_counter() - start) * 1000
    
    print(f"  筛选结果: {len(df_filtered)} 行")
    print(f"  筛选耗时: {elapsed_filter:.2f}ms")
    
    # 缓存统计
    print("\n【缓存统计】")
    stats = service.get_cache_stats()
    print(f"  缓存条目数: {stats['cache_count']}")
    for entry in stats['entries']:
        print(f"    - {entry['key'][:50]}: hit={entry['hit_count']}, age={entry['age_seconds']:.1f}s")


def test_original_vs_optimized():
    """对比原版和优化版"""
    print("\n" + "="*80)
    print("对比原版 vs 优化版")
    print("="*80)
    
    test_date = "2025-11-20"
    test_conditions = [
        {"field": "close", "operator": ">", "value": 10},
        {"field": "pe", "operator": "<", "value": 50},
    ]
    
    # 测试原版
    print("\n【原版流程】")
    from server.routes.screener_routes import (
        get_all_stocks_daily_df,
        merge_factor_data,
        apply_filter_conditions_pl
    )
    
    start_total = time.perf_counter()
    
    start = time.perf_counter()
    df_orig = get_all_stocks_daily_df(target_date=test_date)
    elapsed_load = (time.perf_counter() - start) * 1000
    print(f"  get_all_stocks_daily_df: {elapsed_load:.2f}ms")
    
    if df_orig is not None:
        start = time.perf_counter()
        df_orig = merge_factor_data(df_orig, test_date)
        elapsed_merge = (time.perf_counter() - start) * 1000
        print(f"  merge_factor_data: {elapsed_merge:.2f}ms")
        
        start = time.perf_counter()
        df_filtered_orig = apply_filter_conditions_pl(df_orig, test_conditions, "AND")
        elapsed_filter = (time.perf_counter() - start) * 1000
        print(f"  apply_filter: {elapsed_filter:.2f}ms")
        
        elapsed_total_orig = (time.perf_counter() - start_total) * 1000
        print(f"  总耗时: {elapsed_total_orig:.2f}ms")
        print(f"  结果: {len(df_filtered_orig)} 行")
    
    # 测试优化版
    print("\n【优化版流程】")
    from server.routes.screener_data_service import get_screener_service
    
    service = get_screener_service()
    
    start_total = time.perf_counter()
    
    start = time.perf_counter()
    df_opt = service.get_data(date=test_date, conditions=test_conditions)
    elapsed_load_opt = (time.perf_counter() - start) * 1000
    print(f"  get_data: {elapsed_load_opt:.2f}ms")
    
    if df_opt is not None:
        start = time.perf_counter()
        df_filtered_opt = service.apply_filter_optimized(df_opt, test_conditions, "AND")
        elapsed_filter_opt = (time.perf_counter() - start) * 1000
        print(f"  apply_filter: {elapsed_filter_opt:.2f}ms")
        
        elapsed_total_opt = (time.perf_counter() - start_total) * 1000
        print(f"  总耗时: {elapsed_total_opt:.2f}ms")
        print(f"  结果: {len(df_filtered_opt)} 行")
    
    # 对比
    if df_orig is not None and df_opt is not None:
        print("\n【性能对比】")
        print(f"  原版总耗时: {elapsed_total_orig:.2f}ms")
        print(f"  优化版总耗时: {elapsed_total_opt:.2f}ms")
        print(f"  提速: {elapsed_total_orig/elapsed_total_opt:.1f}x")


def test_column_selection():
    """测试列选择优化"""
    print("\n" + "="*80)
    print("测试列选择优化")
    print("="*80)
    
    from server.routes.screener_data_service import get_screener_service
    
    service = get_screener_service()
    
    test_date = "2025-11-20"
    
    # 只请求少量列
    minimal_fields = ["close", "pe"]
    
    print(f"\n【只读 {len(minimal_fields)} 列】")
    start = time.perf_counter()
    df_minimal = service.get_data(date=test_date, fields=minimal_fields)
    elapsed_minimal = (time.perf_counter() - start) * 1000
    
    if df_minimal is not None:
        print(f"  列数: {len(df_minimal.columns)}")
        print(f"  耗时: {elapsed_minimal:.2f}ms")
    
    # 请求更多列
    more_fields = ["close", "pe", "ma5", "ma10", "ma20", "rsi_6", "macd_dif", "kdj_k"]
    
    print(f"\n【读取 {len(more_fields)} 列】")
    start = time.perf_counter()
    df_more = service.get_data(date=test_date, fields=more_fields)
    elapsed_more = (time.perf_counter() - start) * 1000
    
    if df_more is not None:
        print(f"  列数: {len(df_more.columns)}")
        print(f"  耗时: {elapsed_more:.2f}ms")


def test_api_endpoint():
    """测试优化版 API 端点"""
    print("\n" + "="*80)
    print("测试优化版 API 端点")
    print("="*80)
    
    import requests
    
    url = "http://localhost:5000/api/screener/filter-optimized"
    
    payload = {
        "date": "2025-11-20",
        "conditions": [
            {"field": "close", "operator": ">", "value": 10},
            {"field": "pe", "operator": "<", "value": 50},
        ],
        "logic": "AND",
        "page": 1,
        "page_size": 20
    }
    
    try:
        print(f"\n请求: POST {url}")
        print(f"数据: {payload}")
        
        start = time.perf_counter()
        response = requests.post(url, json=payload, timeout=30)
        elapsed = (time.perf_counter() - start) * 1000
        
        print(f"\n响应状态: {response.status_code}")
        print(f"网络耗时: {elapsed:.2f}ms")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                result = data.get('data', {})
                print(f"总记录数: {result.get('total')}")
                print(f"返回记录: {len(result.get('records', []))}")
                
                perf = result.get('_performance', {})
                print(f"服务端耗时: {perf.get('elapsed_ms')}ms")
                print(f"缓存命中: {perf.get('cache_hits')}")
            else:
                print(f"错误: {data.get('error')}")
        else:
            print(f"响应内容: {response.text[:500]}")
            
    except requests.exceptions.ConnectionError:
        print("无法连接到服务器，请确保 Flask 服务已启动")
    except Exception as e:
        print(f"请求失败: {e}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Stock Screener 优化性能测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 测试优化服务
    test_optimized_service()
    
    # 对比原版和优化版
    test_original_vs_optimized()
    
    # 测试列选择
    test_column_selection()
    
    # 测试 API 端点（需要服务器运行）
    # test_api_endpoint()
    
    print("\n" + "="*80)
    print("测试完成")
    print("="*80)
