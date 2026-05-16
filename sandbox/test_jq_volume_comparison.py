"""
对比聚宽量比策略三个版本

v1: 原版（757行，逐日查询）
v2: 因子库版（242行，向量化）
v3: 声明式版（~80行，声明式因子）
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd


def create_mock_data(T=250, N=100):
    """创建模拟数据"""
    trading_dates = pd.date_range('2024-01-01', periods=T).strftime('%Y-%m-%d').tolist()
    stock_codes = [f'{i:06d}' for i in range(N)]
    
    np.random.seed(42)
    
    # 模拟因子数据
    factors = {
        'close': np.abs(np.cumsum(np.random.randn(T, N) * 0.02, axis=0) + 10).astype(np.float32),
        'open': np.abs(np.random.randn(T, N) * 0.5 + 10).astype(np.float32),
        'high': np.abs(np.random.randn(T, N) * 0.5 + 10.5).astype(np.float32),
        'low': np.abs(np.random.randn(T, N) * 0.5 + 9.5).astype(np.float32),
        'volume': np.abs(np.random.randn(T, N) * 1e6 + 2e6).astype(np.float32),
        'amount': np.abs(np.random.randn(T, N) * 1e7 + 2e7).astype(np.float32),
        'total_mv': np.abs(np.random.randn(T, N) * 30_0000 + 40_0000).astype(np.float32),
        'volume_ratio': np.abs(np.random.randn(T, N) * 1 + 2).astype(np.float32),
        'turnover_rate': np.abs(np.random.randn(T, N) * 2 + 3).astype(np.float32),
        'is_st': np.zeros((T, N), dtype=np.float32),
        'ma5': np.abs(np.random.randn(T, N) * 0.3 + 10).astype(np.float32),
        'days_listed': np.abs(np.random.randn(T, N) * 100 + 200).astype(np.float32),
    }
    
    return trading_dates, stock_codes, factors


def test_v3_strategy():
    """测试 v3 声明式版本"""
    print("\n" + "=" * 60)
    print("v3: 声明式因子版本")
    print("=" * 60)
    
    from core.strategies.jq_volume_strategy_v3 import JQVolumeStrategy
    
    trading_dates, stock_codes, factors = create_mock_data()
    T, N = len(trading_dates), len(stock_codes)
    
    strategy = JQVolumeStrategy()
    
    print(f"\n策略配置:")
    print(f"  required_factors: {strategy.required_factors}")
    print(f"  代码行数: ~80 行")
    
    # 注入因子
    strategy.factors = factors
    
    # 运行
    t0 = time.perf_counter()
    signals = strategy._generate_signals(factors, trading_dates, stock_codes)
    t1 = time.perf_counter()
    
    buy_count = np.sum(signals == 1)
    sell_count = np.sum(signals == 2)
    
    print(f"\n执行结果:")
    print(f"  执行时间: {(t1-t0)*1000:.2f}ms")
    print(f"  买入信号: {buy_count}")
    print(f"  卖出信号: {sell_count}")


def test_function_version():
    """测试函数版本"""
    print("\n" + "=" * 60)
    print("函数策略版本（第二层）")
    print("=" * 60)
    
    from core.strategies.jq_volume_strategy_v3 import jq_volume_func
    from core.strategies.strategy_layers import FunctionStrategy, Position
    
    strategy = FunctionStrategy(
        jq_volume_func,
        required_factors=['close', 'open', 'total_mv', 'volume_ratio', 'is_st', 'ma5', 'days_listed']
    )
    
    print(f"\n策略函数: jq_volume_func")
    print(f"所需因子: {strategy.required_factors}")
    print(f"代码行数: ~15 行（核心逻辑）")
    
    # 模拟单日数据
    stock_pool = pd.DataFrame({
        'stock_code': ['601988', '600000', '000001'],
        'close': [3.5, 10.2, 15.8],
        'open': [3.3, 9.8, 16.0],
        'total_mv': [40_0000, 35_0000, 80_0000],
        'volume_ratio': [3.5, 2.8, 1.5],
        'is_st': [0, 0, 0],
        'ma5': [3.4, 10.0, 15.5],
        'days_listed': [200, 150, 300],
    })
    
    signals = strategy.generate_signals('2024-01-15', stock_pool, None)
    print(f"\n当日信号: {signals}")


def show_comparison():
    """展示对比结果"""
    print("\n" + "=" * 60)
    print("代码量对比")
    print("=" * 60)
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v1: 原版（逐日查询）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

文件: jq_volume_strategy.py
代码行数: 757 行
模式: 逐日查询数据库
性能: O(T × query_time)
特点: 
  - 完整的配置系统
  - 复杂的缓存逻辑
  - 大量防御性代码

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v2: 因子库版（向量化）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

文件: jq_volume_strategy_v2.py
代码行数: 242 行（-68%）
模式: 向量化计算
性能: O(T × N) 向量化
特点:
  - 使用 FactorLoader
  - 保留完整配置系统
  - 大量属性代理代码

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v3: 声明式版本（推荐）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

文件: jq_volume_strategy_v3.py
代码行数: ~80 行（-89%）
模式: 声明式因子 + 向量化
性能: O(T × N) 向量化
特点:
  ✅ 声明 required_factors，自动注入
  ✅ 核心逻辑清晰（买入条件 + 卖出条件）
  ✅ 无需关心因子计算细节

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

函数版本（第二层）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

代码行数: ~15 行（核心逻辑）
模式: 逐日调用
特点:
  ✅ 最简单的编写方式
  ✅ 可访问持仓状态
  ✅ 适合需要状态管理的策略

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

核心代码对比
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v1 原版买入逻辑（简化）:
    def _evaluate_buy_candidates(self, pre_screened_codes, stock_pool_snapshot):
        candidates = stock_pool_snapshot[stock_pool_snapshot["stock_code"].isin(pre_screened_codes)].copy()
        candidates = candidates.drop_duplicates(subset=["stock_code"])
        candidates["volume_ratio"] = candidates["volume_ratio"].fillna(0)
        momentum_mask = ((candidates["close"] / candidates["ma5"]) - 1) >= self.config.momentum_threshold
        big_yang_mask = candidates["close"] >= candidates["open"] * 1.03
        pullback_mask = ((candidates["high"] - candidates["close"]) / candidates["close"]) <= 0.03
        limit_up_mask = ~candidates["is_limit_up"].fillna(False)
        final_mask = (
            (candidates["volume_ratio"] > self.config.volume_ratio_threshold)
            & momentum_mask & big_yang_mask & pullback_mask & limit_up_mask
        )
        return candidates.loc[final_mask, "stock_code"].tolist()

v3 声明式版本:
    def _generate_signals(self, factors, trading_dates, stock_codes):
        # 买入条件
        buy_condition = (
            (total_mv >= self.params.market_cap_min) &
            (total_mv <= self.params.market_cap_max) &
            (volume_ratio > self.params.volume_ratio_threshold) &
            (is_st == 0) &
            (days_listed >= self.params.min_list_days) &
            (close >= open_p * 1.03)
        )
        
        # 卖出条件
        sell_condition = close < ma5
        
        # 生成信号
        signals[1:][buy_condition[:-1]] = 1
        signals[1:][sell_condition[:-1]] = 2
        return signals

函数版本:
    def jq_volume_func(date, factors, position, history):
        if not position.has_position:
            if (20_0000 <= factors['total_mv'] <= 60_0000 and
                factors['volume_ratio'] > 3.0 and
                factors['close'] >= factors['open'] * 1.03):
                return 'buy', 0.2
        else:
            if factors['close'] < factors['ma5']:
                return 'sell', None
        return 'hold', None

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    test_v3_strategy()
    test_function_version()
    show_comparison()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
