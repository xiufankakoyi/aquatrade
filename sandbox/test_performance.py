#!/usr/bin/env python3
"""
测试性能优化效果
"""
import sys
import os
import time
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_trading_dates_performance():
    """测试获取交易日期的性能"""
    print("=" * 60)
    print("测试获取交易日期性能")
    print("=" * 60)
    
    query = OptimizedStockDataQuery()
    
    # 等待预加载完成
    print("等待交易日期预加载...")
    time.sleep(2)
    
    # 测试1: 获取特定范围的交易日期
    start_time = time.perf_counter()
    dates = query.get_trading_dates("2024-05-20", "2025-01-15")
    end_time = time.perf_counter()
    print(f"获取 2024-05-20 到 2025-01-15 的交易日期: {len(dates)} 个, 耗时: {end_time - start_time:.3f}s")
    
    # 测试2: 再次获取相同范围（应该命中缓存）
    start_time = time.perf_counter()
    dates = query.get_trading_dates("2024-05-20", "2025-01-15")
    end_time = time.perf_counter()
    print(f"再次获取相同范围: {len(dates)} 个, 耗时: {end_time - start_time:.3f}s")
    
    # 测试3: 获取另一个范围
    start_time = time.perf_counter()
    dates = query.get_trading_dates("2024-01-21", "2024-05-20")
    end_time = time.perf_counter()
    print(f"获取 2024-01-21 到 2024-05-20 的交易日期: {len(dates)} 个, 耗时: {end_time - start_time:.3f}s")

def test_limit_status_performance():
    """测试获取涨跌停数据的性能"""
    print("\n" + "=" * 60)
    print("测试涨跌停数据加载性能")
    print("=" * 60)
    
    query = OptimizedStockDataQuery()
    
    # 测试加载涨跌停数据
    start_time = time.perf_counter()
    df = query.get_all_daily_data_for_period("2024-02-20", "2025-01-15")
    end_time = time.perf_counter()
    print(f"加载 2024-02-20 到 2025-01-15 的所有数据: {len(df)} 行, 耗时: {end_time - start_time:.3f}s")

if __name__ == "__main__":
    test_trading_dates_performance()
    test_limit_status_performance()
