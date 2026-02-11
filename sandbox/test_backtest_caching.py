#!/usr/bin/env python3
"""
测试回测结果缓存性能
"""
import sys
import os
import time
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 简单测试策略类
class SimpleTestStrategy:
    def __init__(self):
        self.name = "SimpleTestStrategy"
        self.strategy_name = "SimpleTestStrategy"
        self.warmup_days = 60
        self.max_positions = 3
        self.position_ratio = 0.2
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data=None):
        """向量化信号生成"""
        import numpy as np
        T, N, _ = price_matrix.shape
        # 生成随机信号（1=buy, 0=hold, 2=sell）
        signal_matrix = np.random.randint(0, 3, size=(T, N), dtype=np.int32)
        return signal_matrix

def test_backtest_caching():
    """测试回测结果缓存性能"""
    print("=" * 60)
    print("测试回测结果缓存性能")
    print("=" * 60)
    
    # 初始化数据查询和回测引擎
    data_query = OptimizedStockDataQuery()
    backtest_engine = OptimizedBacktestEngine(data_query, initial_capital=1000000)
    
    # 创建测试策略
    strategy = SimpleTestStrategy()
    
    # 测试日期范围
    start_date = "2024-05-20"
    end_date = "2025-01-15"
    
    # 第一次回测（应该缓存结果）
    print("\n1. 第一次回测（预期：慢，结果会被缓存）...")
    start_time = time.perf_counter()
    
    # 执行回测并收集结果
    final_metrics = None
    all_trades = []
    
    # 使用生成器获取结果
    results = []
    for result in backtest_engine.run_backtest_streaming(start_date, end_date, strategy):
        results.append(result)
        if result["type"] == "final_metrics":
            final_metrics = result["data"]
        elif result["type"] == "new_trade":
            all_trades.append(result["data"])
    
    end_time = time.perf_counter()
    first_time = end_time - start_time
    print(f"   第一次回测耗时: {first_time:.2f}s")
    
    # 打印回测指标，验证修复
    print("\n回测指标验证:")
    if final_metrics:
        print(f"   win_rate: {final_metrics.get('win_rate', 0):.2f}%")
        print(f"   profit_factor: {final_metrics.get('profit_factor', 0):.2f}")
        print(f"   trades_count: {final_metrics.get('trades_count', 0)}")
        print(f"   sell_trades_count: {final_metrics.get('sell_trades_count', 0)}")
        print(f"   total_return: {final_metrics.get('total_return', 0):.2f}%")
        print(f"   sharpe_ratio: {final_metrics.get('sharpe_ratio', 0):.4f}")
    else:
        print("   未获取到回测指标")
    
    # 打印交易记录统计
    print(f"\n交易记录统计:")
    print(f"   总交易数: {len(all_trades)}")
    if all_trades:
        buy_trades = [t for t in all_trades if t["action"] == "buy"]
        sell_trades = [t for t in all_trades if t["action"] == "sell"]
        print(f"   买入交易数: {len(buy_trades)}")
        print(f"   卖出交易数: {len(sell_trades)}")
        
        # 检查是否有profit_loss字段
        has_profit_loss = any("profit_loss" in t for t in sell_trades)
        print(f"   卖出交易包含profit_loss字段: {has_profit_loss}")
        
        # 如果有profit_loss字段，打印一些示例
        if has_profit_loss:
            print(f"   示例卖出交易profit_loss: {sell_trades[0].get('profit_loss', 0):.2f}")
    
    # 第二次回测（应该命中缓存）
    print("\n2. 第二次回测（预期：快，命中缓存）...")
    start_time = time.perf_counter()
    
    results = []
    for result in backtest_engine.run_backtest_streaming(start_date, end_date, strategy):
        results.append(result)
    
    end_time = time.perf_counter()
    second_time = end_time - start_time
    print(f"   第二次回测耗时: {second_time:.2f}s")
    
    # 计算性能提升
    if second_time > 0:
        speedup = first_time / second_time
        print(f"\n3. 性能提升: {speedup:.2f}x")
    else:
        print(f"\n3. 性能提升: 无穷大x（第二次回测耗时为0）")
    
    # 输出缓存统计
    print(f"\n4. 缓存统计:")
    print(f"   缓存命中次数: {backtest_engine._cache_hits}")
    print(f"   缓存未命中次数: {backtest_engine._cache_misses}")
    print(f"   当前缓存大小: {len(backtest_engine._backtest_cache)}/{backtest_engine._cache_max_size}")

if __name__ == "__main__":
    test_backtest_caching()
