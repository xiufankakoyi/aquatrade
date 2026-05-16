#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stock Screener 性能分析工具

包含三种分析方法：
1. cProfile - 函数级性能分析
2. ArcticDB 详细日志 - 查看查询过程中的关键步骤耗时
3. timeit - 微基准测试

使用方法：
    python sandbox/profile_screener_performance.py

输出：
    - 性能分析报告（控制台输出）
    - 火焰图数据（可选导出）
    - 详细的函数调用耗时统计
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import cProfile
import pstats
import io
import time
import timeit
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

import polars as pl
import pandas as pd
import numpy as np

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """性能分析器 - 集成 cProfile、timeit 和日志分析"""
    
    def __init__(self):
        self.timings: Dict[str, List[float]] = {}
        self.arctic_timings: Dict[str, float] = {}
        
    @contextmanager
    def timer(self, name: str):
        """上下文管理器：测量代码块执行时间"""
        start = time.perf_counter()
        logger.debug(f"[TIMER START] {name}")
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if name not in self.timings:
                self.timings[name] = []
            self.timings[name].append(elapsed)
            logger.debug(f"[TIMER END] {name}: {elapsed:.4f}s")
    
    def profile_function(self, func: Callable, *args, **kwargs) -> Any:
        """
        使用 cProfile 分析函数性能
        
        Args:
            func: 要分析的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数返回值
        """
        profiler = cProfile.Profile()
        profiler.enable()
        
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time
        
        profiler.disable()
        
        # 输出分析结果
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(30)  # 打印前30个耗时最多的函数
        
        print(f"\n{'='*80}")
        print(f"cProfile 分析结果: {func.__name__}")
        print(f"总耗时: {elapsed:.4f}s")
        print(f"{'='*80}")
        print(s.getvalue())
        
        return result
    
    def benchmark_function(self, func: Callable, setup: str = '', number: int = 10) -> float:
        """
        使用 timeit 进行微基准测试
        
        Args:
            func: 要测试的函数（字符串形式）
            setup: 设置代码
            number: 运行次数
            
        Returns:
            平均执行时间（秒）
        """
        timer = timeit.Timer(func, setup=setup, globals=globals())
        total_time = timer.timeit(number=number)
        avg_time = total_time / number
        
        print(f"\n[timeit] {func}")
        print(f"  运行次数: {number}")
        print(f"  总耗时: {total_time:.4f}s")
        print(f"  平均耗时: {avg_time:.4f}s")
        
        return avg_time
    
    def print_summary(self):
        """打印所有计时器的汇总统计"""
        print(f"\n{'='*80}")
        print("性能分析汇总")
        print(f"{'='*80}")
        
        for name, times in sorted(self.timings.items()):
            avg_time = sum(times) / len(times)
            total_time = sum(times)
            print(f"{name}:")
            print(f"  调用次数: {len(times)}")
            print(f"  平均耗时: {avg_time:.4f}s")
            print(f"  总耗时: {total_time:.4f}s")
            print(f"  最小/最大: {min(times):.4f}s / {max(times):.4f}s")


# 导入被分析的函数
from server.routes.screener_routes import (
    get_all_stocks_daily_df,
    get_factor_data_for_date,
    merge_factor_data,
    apply_filter_conditions_pl,
    filter_stocks
)
from data_svc.storage.arcticdb_manager import get_arctic_instance, get_arctic_instance_for_library


def profile_get_all_stocks_daily_df():
    """分析 get_all_stocks_daily_df 函数性能"""
    print("\n" + "="*80)
    print("分析: get_all_stocks_daily_df (从 Parquet/ArcticDB 加载数据)")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    # 使用 cProfile 分析
    target_date = "2025-11-20"
    result = profiler.profile_function(get_all_stocks_daily_df, target_date)
    
    if result is not None:
        print(f"数据加载成功: {len(result)} 行")
    
    return result


def profile_arcticdb_read():
    """分析 ArcticDB 读取性能"""
    print("\n" + "="*80)
    print("分析: ArcticDB 读取性能")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    # 获取 ArcticDB 实例
    with profiler.timer("get_arctic_instance"):
        arctic = get_arctic_instance()
    
    if "stock_daily" not in arctic.list_libraries():
        print("stock_daily 库不存在")
        return
    
    lib = arctic["stock_daily"]
    symbols = lib.list_symbols()
    print(f"库中共有 {len(symbols)} 个 symbols")
    
    # 分析读取单个 symbol
    if symbols:
        test_symbol = symbols[0]
        print(f"\n测试读取 symbol: {test_symbol}")
        
        with profiler.timer(f"read_symbol_{test_symbol}"):
            data = lib.read(test_symbol)
        
        print(f"数据类型: {type(data.data)}")
        if hasattr(data.data, 'shape'):
            print(f"数据形状: {data.data.shape}")
    
    # 分析读取统一 symbol（如果存在）
    if "stock_daily" in symbols:
        print("\n测试读取统一 stock_daily symbol")
        
        with profiler.timer("read_unified_stock_daily"):
            data = lib.read("stock_daily")
        
        raw_data = data.data
        print(f"原始数据类型: {type(raw_data)}")
        
        # 分析转换为 Polars 的性能
        with profiler.timer("convert_to_polars"):
            if hasattr(raw_data, 'to_pandas'):
                df = pl.from_arrow(raw_data)
            elif hasattr(raw_data, 'empty'):
                df = pl.from_pandas(raw_data)
            else:
                df = raw_data
        
        print(f"Polars DataFrame 形状: {df.shape if hasattr(df, 'shape') else 'N/A'}")
    
    profiler.print_summary()


def profile_merge_factor_data():
    """分析因子数据合并性能"""
    print("\n" + "="*80)
    print("分析: merge_factor_data (合并因子数据)")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    # 先加载股票数据
    target_date = "2025-11-20"
    stock_df = get_all_stocks_daily_df(target_date)
    
    if stock_df is None or stock_df.is_empty():
        print("无法获取股票数据")
        return
    
    print(f"股票数据: {len(stock_df)} 行")
    
    # 使用 cProfile 分析合并过程
    result = profiler.profile_function(merge_factor_data, stock_df, target_date)
    
    if result is not None:
        print(f"合并后数据: {len(result)} 行")
    
    return result


def profile_filter_conditions():
    """分析筛选条件应用性能"""
    print("\n" + "="*80)
    print("分析: apply_filter_conditions_pl (应用筛选条件)")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    # 准备测试数据
    target_date = "2025-11-20"
    df = get_all_stocks_daily_df(target_date)
    
    if df is None:
        print("无法获取数据")
        return
    
    # 合并因子数据
    df = merge_factor_data(df, target_date)
    print(f"测试数据: {len(df)} 行, {len(df.columns)} 列")
    
    # 测试不同的筛选条件
    test_conditions = [
        # 简单条件
        [{"field": "close", "operator": ">", "value": 10}],
        # 多个条件 AND
        [
            {"field": "close", "operator": ">", "value": 10},
            {"field": "pe", "operator": "<", "value": 50},
        ],
        # 范围条件
        [{"field": "close", "operator": "between", "value": 10, "value2": 100}],
    ]
    
    for i, conditions in enumerate(test_conditions):
        print(f"\n测试条件 {i+1}: {conditions}")
        
        with profiler.timer(f"filter_conditions_{i+1}"):
            result = apply_filter_conditions_pl(df, conditions, "AND")
        
        print(f"  筛选结果: {len(result)} 行")
    
    profiler.print_summary()


def profile_full_filter_pipeline():
    """分析完整的筛选流程"""
    print("\n" + "="*80)
    print("分析: 完整筛选流程 (filter_stocks)")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    # 模拟 API 请求数据
    test_request_data = {
        "date": "2025-11-20",
        "conditions": [
            {"field": "close", "operator": ">", "value": 10},
            {"field": "pe", "operator": "<", "value": 50},
        ],
        "logic": "AND",
        "page": 1,
        "page_size": 20,
    }
    
    # 手动执行筛选流程的各个步骤
    target_date = test_request_data["date"]
    conditions = test_request_data["conditions"]
    
    # 步骤1: 获取数据
    with profiler.timer("step1_get_all_stocks_daily_df"):
        df = get_all_stocks_daily_df(target_date)
    
    if df is None:
        print("无法获取数据")
        return
    
    print(f"步骤1 - 获取数据: {len(df)} 行, 耗时 {profiler.timings['step1_get_all_stocks_daily_df'][-1]:.4f}s")
    
    # 步骤2: 合并因子数据
    with profiler.timer("step2_merge_factor_data"):
        df = merge_factor_data(df, target_date)
    
    print(f"步骤2 - 合并因子: {len(df)} 行, 耗时 {profiler.timings['step2_merge_factor_data'][-1]:.4f}s")
    
    # 步骤3: 应用筛选条件
    with profiler.timer("step3_apply_filter"):
        df_filtered = apply_filter_conditions_pl(df, conditions, "AND")
    
    total = len(df_filtered)
    print(f"步骤3 - 应用筛选: {total} 行, 耗时 {profiler.timings['step3_apply_filter'][-1]:.4f}s")
    
    # 步骤4: 排序
    with profiler.timer("step4_sort"):
        if "total_mv" in df_filtered.columns:
            df_filtered = df_filtered.sort("total_mv", descending=True)
    
    print(f"步骤4 - 排序: 耗时 {profiler.timings['step4_sort'][-1]:.4f}s")
    
    # 步骤5: 分页
    with profiler.timer("step5_pagination"):
        page_size = test_request_data["page_size"]
        df_paged = df_filtered.slice(0, page_size)
    
    print(f"步骤5 - 分页: {len(df_paged)} 行, 耗时 {profiler.timings['step5_pagination'][-1]:.4f}s")
    
    # 步骤6: 转换为字典
    with profiler.timer("step6_to_dict"):
        result_pdf = df_paged.to_pandas()
        records = result_pdf.to_dict("records")
    
    print(f"步骤6 - 转字典: {len(records)} 条记录, 耗时 {profiler.timings['step6_to_dict'][-1]:.4f}s")
    
    profiler.print_summary()
    
    return records


def profile_parquet_vs_arcticdb():
    """对比 Parquet 和 ArcticDB 的读取性能"""
    print("\n" + "="*80)
    print("对比: Parquet vs ArcticDB 读取性能")
    print("="*80)
    
    profiler = PerformanceProfiler()
    
    import os
    parquet_path = os.path.join(
        project_root, 'data', 'parquet_data', 'stock_daily.parquet'
    )
    
    # 测试 Parquet 读取
    if os.path.exists(parquet_path):
        print(f"\n测试 Parquet 读取: {parquet_path}")
        
        with profiler.timer("parquet_read_full"):
            df_parquet = pl.read_parquet(parquet_path)
        
        print(f"  Parquet 数据: {len(df_parquet)} 行")
        
        # 测试带过滤的 Parquet 读取
        target_date = "2025-11-20"
        with profiler.timer("parquet_read_filtered"):
            df_filtered = pl.scan_parquet(parquet_path).filter(
                pl.col("trade_date") == target_date
            ).collect()
        
        print(f"  Parquet 过滤后: {len(df_filtered)} 行")
    else:
        print(f"Parquet 文件不存在: {parquet_path}")
    
    # 测试 ArcticDB 读取
    print("\n测试 ArcticDB 读取:")
    
    with profiler.timer("arcticdb_get_instance"):
        arctic = get_arctic_instance()
    
    if "stock_daily" in arctic.list_libraries():
        lib = arctic["stock_daily"]
        
        with profiler.timer("arcticdb_list_symbols"):
            symbols = lib.list_symbols()
        
        print(f"  Symbols 数量: {len(symbols)}")
        
        if "stock_daily" in symbols:
            with profiler.timer("arcticdb_read_unified"):
                data = lib.read("stock_daily")
            
            raw_data = data.data
            with profiler.timer("arcticdb_convert_polars"):
                if hasattr(raw_data, 'to_pandas'):
                    df_arctic = pl.from_arrow(raw_data)
                elif hasattr(raw_data, 'empty'):
                    df_arctic = pl.from_pandas(raw_data)
                else:
                    df_arctic = raw_data
            
            print(f"  ArcticDB 数据: {len(df_arctic)} 行")
    
    profiler.print_summary()


def run_all_profiles():
    """运行所有性能分析"""
    print("\n" + "="*80)
    print("Stock Screener 性能分析工具")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    try:
        # 1. 分析 ArcticDB 读取性能
        profile_arcticdb_read()
        
        # 2. 对比 Parquet vs ArcticDB
        profile_parquet_vs_arcticdb()
        
        # 3. 分析数据加载
        profile_get_all_stocks_daily_df()
        
        # 4. 分析因子合并
        profile_merge_factor_data()
        
        # 5. 分析筛选条件
        profile_filter_conditions()
        
        # 6. 分析完整流程
        profile_full_filter_pipeline()
        
    except Exception as e:
        print(f"\n分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("性能分析完成")
    print("="*80)


if __name__ == "__main__":
    run_all_profiles()
