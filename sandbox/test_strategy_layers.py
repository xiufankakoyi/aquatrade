"""
测试三层策略系统

展示三种策略编写方式：
1. 函数策略（中等）- 简单 Python 函数
2. 类策略简化版 - 声明式因子
3. 预置策略模板 - 一行代码
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd


def test_function_strategy():
    """
    第二层：函数策略（中等难度）
    
    用户写一个简单函数，引擎逐日调用。
    """
    print("\n" + "=" * 60)
    print("第二层：函数策略")
    print("=" * 60)
    
    from core.strategies.strategy_layers import FunctionStrategy, Position
    
    # 用户只需写这个函数
    def my_dual_ma(date: str, factors: dict, position: Position, history: list):
        """
        策略逻辑：
        - 无持仓时，MA5 > MA10 且成交量放大 -> 买入
        - 有持仓时，MA5 < MA10 -> 卖出
        """
        ma5 = factors.get('ma5', 0)
        ma10 = factors.get('ma10', 0)
        volume = factors.get('volume', 0)
        
        if not position.has_position:
            if ma5 > ma10 and volume > 1e6:
                return 'buy', 0.1  # 买入 10% 仓位
        else:
            if ma5 < ma10:
                return 'sell', None  # 全卖
        
        return 'hold', None
    
    # 创建策略
    strategy = FunctionStrategy(
        signal_func=my_dual_ma,
        required_factors=['ma5', 'ma10', 'volume']
    )
    
    print(f"\n策略函数: {strategy.name}")
    print(f"所需因子: {strategy.required_factors}")
    
    # 模拟单日数据
    stock_pool = pd.DataFrame({
        'stock_code': ['601988', '600000', '000001'],
        'close': [3.5, 10.2, 15.8],
        'ma5': [3.4, 10.5, 15.6],
        'ma10': [3.3, 10.0, 15.9],
        'volume': [2e6, 1.5e6, 0.8e6],
    })
    
    signals = strategy.generate_signals('2024-01-15', stock_pool, None)
    print(f"\n当日信号: {signals}")


def test_simple_strategy():
    """
    第三层简化版：声明式向量化策略
    
    用户声明因子，使用内置信号函数。
    """
    print("\n" + "=" * 60)
    print("第三层：声明式向量化策略")
    print("=" * 60)
    
    from core.strategies.strategy_layers import SimpleStrategy
    from core.strategies.utils.signal_utils import crossover, crossunder
    
    class MyStrategy(SimpleStrategy):
        """自定义策略 - 只需 10 行代码"""
        required_factors = ['ma5', 'ma10', 'rsi_14']
        
        def _generate_signals(self, factors, trading_dates, stock_codes):
            T, N = len(trading_dates), len(stock_codes)
            signals = np.zeros((T, N), dtype=np.int32)
            
            ma5 = factors['ma5']
            ma10 = factors['ma10']
            rsi = factors['rsi_14']
            
            # 金叉 + RSI 超卖 -> 买入
            golden = crossover(ma5, ma10)
            oversold = rsi[1:] < 30
            signals[1:][golden & oversold] = 1
            
            # 死叉 -> 卖出
            death = crossunder(ma5, ma10)
            signals[1:][death] = 2
            
            return signals
    
    strategy = MyStrategy(name="my_strategy")
    print(f"\n策略: {strategy.strategy_name}")
    print(f"所需因子: {strategy.required_factors}")
    
    # 模拟数据测试
    T, N = 100, 50
    trading_dates = pd.date_range('2024-01-01', periods=T).strftime('%Y-%m-%d').tolist()
    stock_codes = [f'{i:06d}' for i in range(N)]
    
    np.random.seed(42)
    price_matrix = np.random.randn(T, N, 4).astype(np.float32) * 2 + 10
    
    # 模拟因子
    factors = {
        'ma5': np.random.randn(T, N).astype(np.float32) * 0.5 + 10,
        'ma10': np.random.randn(T, N).astype(np.float32) * 0.3 + 10,
        'rsi_14': np.random.rand(T, N).astype(np.float32) * 100,
    }
    
    strategy.factors = factors
    
    t0 = time.perf_counter()
    signals = strategy._generate_signals(factors, trading_dates, stock_codes)
    t1 = time.perf_counter()
    
    print(f"\n执行时间: {(t1-t0)*1000:.2f}ms")
    print(f"买入信号: {np.sum(signals == 1)}")
    print(f"卖出信号: {np.sum(signals == 2)}")


def test_preset_strategies():
    """
    预置策略模板 - 一行代码
    """
    print("\n" + "=" * 60)
    print("预置策略模板")
    print("=" * 60)
    
    from core.strategies.strategy_layers import (
        DualMAStrategy, RSIStrategy, MACDStrategy, BollingerStrategy
    )
    
    # 双均线策略 - 一行代码
    ma_strategy = DualMAStrategy(fast=5, slow=10)
    print(f"\n双均线策略: {ma_strategy.required_factors}")
    
    # RSI 策略
    rsi_strategy = RSIStrategy(oversold=30, overbought=70)
    print(f"RSI 策略: {rsi_strategy.required_factors}")
    
    # MACD 策略
    macd_strategy = MACDStrategy()
    print(f"MACD 策略: {macd_strategy.required_factors}")
    
    # 布林带策略
    boll_strategy = BollingerStrategy()
    print(f"布林带策略: {boll_strategy.required_factors}")
    
    # 模拟测试
    T, N = 100, 50
    trading_dates = pd.date_range('2024-01-01', periods=T).strftime('%Y-%m-%d').tolist()
    stock_codes = [f'{i:06d}' for i in range(N)]
    
    np.random.seed(42)
    
    # 模拟因子数据
    factors = {
        'ma5': np.random.randn(T, N).astype(np.float32) * 0.5 + 10,
        'ma10': np.random.randn(T, N).astype(np.float32) * 0.3 + 10,
        'rsi_14': np.random.rand(T, N).astype(np.float32) * 100,
        'macd_dif': np.random.randn(T, N).astype(np.float32) * 0.1,
        'macd_dea': np.random.randn(T, N).astype(np.float32) * 0.08,
        'boll_upper': np.random.randn(T, N).astype(np.float32) * 0.5 + 11,
        'boll_lower': np.random.randn(T, N).astype(np.float32) * 0.5 + 9,
        'close': np.random.randn(T, N).astype(np.float32) * 0.5 + 10,
    }
    
    print("\n策略执行结果:")
    
    for name, strategy in [
        ('双均线', ma_strategy),
        ('RSI', rsi_strategy),
        ('MACD', macd_strategy),
        ('布林带', boll_strategy),
    ]:
        strategy.factors = factors
        signals = strategy._generate_signals(factors, trading_dates, stock_codes)
        print(f"  {name}: 买入={np.sum(signals == 1)}, 卖出={np.sum(signals == 2)}")


def show_code_comparison():
    """展示代码量对比"""
    print("\n" + "=" * 60)
    print("代码量对比")
    print("=" * 60)
    
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

第二层：函数策略（中等难度）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def my_strategy(date, factors, position, history):
    if not position.has_position and factors['ma5'] > factors['ma10']:
        return 'buy', 0.1
    elif position.has_position and factors['ma5'] < factors['ma10']:
        return 'sell', None
    return 'hold', None

strategy = FunctionStrategy(my_strategy, required_factors=['ma5', 'ma10'])

特点：
  ✅ 逐日调用，逻辑直观
  ✅ 可访问持仓状态和历史
  ✅ 适合需要状态管理的策略

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

第三层：声明式向量化策略
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MyStrategy(SimpleStrategy):
    required_factors = ['ma5', 'ma10']
    
    def _generate_signals(self, factors, trading_dates, stock_codes):
        golden = crossover(factors['ma5'], factors['ma10'])
        death = crossunder(factors['ma5'], factors['ma10'])
        
        signals = np.zeros(factors['ma5'].shape, dtype=int)
        signals[1:][golden] = 1
        signals[1:][death] = 2
        return signals

特点：
  ✅ 向量化计算，性能最优
  ✅ 使用内置信号函数（crossover, crossunder 等）
  ✅ 适合专业用户

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

预置策略模板（最简单）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 双均线策略
strategy = DualMAStrategy(fast=5, slow=10)

# RSI 策略
strategy = RSIStrategy(oversold=30, overbought=70)

# MACD 策略
strategy = MACDStrategy()

# 布林带策略
strategy = BollingerStrategy()

特点：
  ✅ 一行代码创建策略
  ✅ 内置常用策略逻辑
  ✅ 适合快速验证

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

内置信号函数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

crossover(fast, slow)    # 金叉检测
crossunder(fast, slow)   # 死叉检测
above(series, threshold) # 上穿阈值
below(series, threshold) # 下穿阈值
rising(series, window)   # 连续上涨
falling(series, window)  # 连续下跌
in_range(series, low, high)  # 区间检测
breakout(upper, lower, close) # 突破检测

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    test_function_strategy()
    test_simple_strategy()
    test_preset_strategies()
    show_code_comparison()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
