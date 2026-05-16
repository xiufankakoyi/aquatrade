#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stock Screener API 性能分析装饰器

使用方法:
1. 直接运行测试: python sandbox/screener_api_profiler.py
2. 在 screener_routes.py 中导入装饰器使用

特性:
- 自动记录每个步骤的耗时
- 输出详细的性能报告
- 支持 ArcticDB 日志级别调整
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import functools
import time
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

import polars as pl
import pandas as pd


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ScreenerProfiler")


@dataclass
class StepTiming:
    """步骤计时数据类"""
    step_name: str
    start_time: float
    end_time: float
    duration_ms: float
    details: Dict[str, Any] = None
    
    def to_dict(self):
        return {
            'step_name': self.step_name,
            'duration_ms': round(self.duration_ms, 2),
            'details': self.details or {}
        }


class ScreenerProfiler:
    """
    Stock Screener 性能分析器
    
    用于分析 filter_stocks API 的各个步骤耗时
    """
    
    def __init__(self):
        self.steps: List[StepTiming] = []
        self.current_step_start: Optional[float] = None
        self.current_step_name: Optional[str] = None
        
    def start_step(self, step_name: str, details: Dict = None):
        """开始计时一个步骤"""
        self.current_step_name = step_name
        self.current_step_start = time.perf_counter()
        logger.info(f"[START] {step_name}")
        
    def end_step(self, details: Dict = None):
        """结束当前步骤计时"""
        if self.current_step_start is None:
            return
            
        end_time = time.perf_counter()
        duration_ms = (end_time - self.current_step_start) * 1000
        
        step = StepTiming(
            step_name=self.current_step_name,
            start_time=self.current_step_start,
            end_time=end_time,
            duration_ms=duration_ms,
            details=details
        )
        self.steps.append(step)
        
        logger.info(f"[END] {self.current_step_name}: {duration_ms:.2f}ms")
        
        self.current_step_start = None
        self.current_step_name = None
        
    def get_summary(self) -> Dict:
        """获取性能汇总报告"""
        total_ms = sum(s.duration_ms for s in self.steps)
        
        return {
            'total_duration_ms': round(total_ms, 2),
            'steps': [s.to_dict() for s in self.steps],
            'slowest_step': max(self.steps, key=lambda x: x.duration_ms).step_name if self.steps else None,
            'step_count': len(self.steps)
        }
    
    def print_report(self):
        """打印性能报告"""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("Stock Screener API 性能报告")
        print("="*80)
        print(f"总耗时: {summary['total_duration_ms']:.2f}ms")
        print(f"步骤数: {summary['step_count']}")
        print(f"最慢步骤: {summary['slowest_step']}")
        print("-"*80)
        print(f"{'步骤名称':<40} {'耗时(ms)':>12} {'占比':>10}")
        print("-"*80)
        
        total = summary['total_duration_ms']
        for step in self.steps:
            pct = (step.duration_ms / total * 100) if total > 0 else 0
            print(f"{step.step_name:<40} {step.duration_ms:>12.2f} {pct:>9.1f}%")
        
        print("="*80)


def profile_screener_api(func):
    """
    性能分析装饰器 - 用于 filter_stocks 函数
    
    用法:
        @profile_screener_api
        def filter_stocks():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = ScreenerProfiler()
        
        # 在函数上下文中注入 profiler
        kwargs['_profiler'] = profiler
        
        start = time.perf_counter()
        result = func(*args, **kwargs)
        total_ms = (time.perf_counter() - start) * 1000
        
        logger.info(f"API 总耗时: {total_ms:.2f}ms")
        profiler.print_report()
        
        # 将性能数据添加到响应中（如果是 JSON 响应）
        if hasattr(result, 'json'):
            try:
                data = result.get_json()
                if isinstance(data, dict) and 'data' in data:
                    data['data']['_performance'] = profiler.get_summary()
            except:
                pass
        
        return result
    
    return wrapper


def enable_arcticdb_debug_logging():
    """
    启用 ArcticDB 的详细调试日志
    
    这有助于分析 ArcticDB 查询过程中的关键步骤耗时
    """
    # 设置 ArcticDB 相关日志级别
    logging.getLogger('arcticdb').setLevel(logging.DEBUG)
    logging.getLogger('arcticdb').addHandler(logging.StreamHandler())
    
    # 设置 LMDB 日志
    logging.getLogger('lmdb').setLevel(logging.DEBUG)
    
    logger.info("ArcticDB 调试日志已启用")


# ============== 测试代码 ==============

def test_profile_filter_stocks():
    """测试 filter_stocks 性能分析"""
    from server.routes.screener_routes import (
        get_all_stocks_daily_df,
        merge_factor_data,
        apply_filter_conditions_pl,
        get_latest_trade_date
    )
    from data_svc.unified_data_query import get_stock_basic
    
    profiler = ScreenerProfiler()
    
    # 模拟请求数据
    test_data = {
        "date": "2025-11-20",
        "conditions": [
            {"field": "close", "operator": ">", "value": 10},
            {"field": "pe", "operator": "<", "value": 50},
        ],
        "logic": "AND",
        "page": 1,
        "page_size": 20,
    }
    
    try:
        # 步骤1: 获取日期
        profiler.start_step("get_date")
        date = test_data.get('date') or get_latest_trade_date()
        profiler.end_step({'date': date})
        
        # 步骤2: 获取股票数据
        profiler.start_step("get_all_stocks_daily_df")
        df = get_all_stocks_daily_df(target_date=date)
        profiler.end_step({
            'rows': len(df) if df is not None else 0,
            'columns': len(df.columns) if df is not None else 0
        })
        
        if df is None or df.is_empty():
            logger.error("无法获取股票数据")
            return
        
        # 步骤3: 添加 stock_code 列
        profiler.start_step("add_stock_code")
        if 'stock_code' not in df.columns and 'ts_code' in df.columns:
            df = df.with_columns(
                pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
            )
        profiler.end_step({'rows': len(df)})
        
        # 步骤4: 添加股票名称
        profiler.start_step("add_stock_names")
        if 'stock_name' not in df.columns:
            try:
                stock_basic_df = get_stock_basic()
                if stock_basic_df is not None and not stock_basic_df.empty:
                    stock_basic_pl = pl.from_pandas(stock_basic_df[['ts_code', 'name']].copy())
                    stock_basic_pl = stock_basic_pl.with_columns(
                        pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
                    )
                    stock_name_map = stock_basic_pl.select(['stock_code', 'name']).unique(subset=['stock_code'])
                    df = df.join(stock_name_map, on='stock_code', how='left')
                    df = df.rename({'name': 'stock_name'})
            except Exception as e:
                logger.warning(f"获取股票名称失败: {e}")
        profiler.end_step({'rows': len(df)})
        
        # 步骤5: 合并因子数据
        profiler.start_step("merge_factor_data")
        df = merge_factor_data(df, date)
        profiler.end_step({
            'rows': len(df),
            'columns': len(df.columns)
        })
        
        # 步骤6: 应用筛选条件
        profiler.start_step("apply_filter_conditions")
        conditions = test_data.get('conditions', [])
        logic = test_data.get('logic', 'AND')
        df_filtered = apply_filter_conditions_pl(df, conditions, logic)
        total = len(df_filtered)
        profiler.end_step({
            'filtered_rows': total,
            'filter_ratio': f"{total/len(df)*100:.1f}%" if len(df) > 0 else "0%"
        })
        
        # 步骤7: 排序
        profiler.start_step("sort_results")
        if 'total_mv' in df_filtered.columns:
            df_filtered = df_filtered.sort('total_mv', descending=True)
        profiler.end_step()
        
        # 步骤8: 分页
        profiler.start_step("pagination")
        page = test_data.get('page', 1)
        page_size = test_data.get('page_size', 20)
        offset = (page - 1) * page_size
        df_paged = df_filtered.slice(offset, page_size)
        profiler.end_step({
            'page': page,
            'page_size': page_size,
            'returned_rows': len(df_paged)
        })
        
        # 步骤9: 转换为字典
        profiler.start_step("convert_to_dict")
        result_pdf = df_paged.to_pandas()
        records = result_pdf.to_dict('records')
        profiler.end_step({'record_count': len(records)})
        
        # 打印报告
        profiler.print_report()
        
        return {
            'success': True,
            'data': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'records': records,
                '_performance': profiler.get_summary()
            }
        }
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        profiler.print_report()
        return {'success': False, 'error': str(e)}


def test_arcticdb_with_logging():
    """测试 ArcticDB 带详细日志的性能"""
    enable_arcticdb_debug_logging()
    
    from data_svc.storage.arcticdb_manager import get_arctic_instance
    
    profiler = ScreenerProfiler()
    
    profiler.start_step("arcticdb_get_instance")
    arctic = get_arctic_instance()
    profiler.end_step()
    
    if "stock_daily" not in arctic.list_libraries():
        logger.error("stock_daily 库不存在")
        return
    
    lib = arctic["stock_daily"]
    
    profiler.start_step("arcticdb_list_symbols")
    symbols = lib.list_symbols()
    profiler.end_step({'symbol_count': len(symbols)})
    
    if "stock_daily" in symbols:
        profiler.start_step("arcticdb_read_data")
        data = lib.read("stock_daily")
        profiler.end_step({'data_type': type(data.data).__name__})
        
        profiler.start_step("convert_to_polars")
        raw_data = data.data
        if hasattr(raw_data, 'to_pandas'):
            df = pl.from_arrow(raw_data)
        elif hasattr(raw_data, 'empty'):
            df = pl.from_pandas(raw_data)
        else:
            df = raw_data
        profiler.end_step({'rows': len(df), 'columns': len(df.columns)})
    
    profiler.print_report()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Stock Screener API 性能分析")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 测试1: 完整 API 流程分析
    print("\n【测试1】完整 API 流程分析")
    result = test_profile_filter_stocks()
    
    # 测试2: ArcticDB 带日志分析
    print("\n【测试2】ArcticDB 带详细日志")
    test_arcticdb_with_logging()
