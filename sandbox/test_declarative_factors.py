"""
测试声明式因子系统

测试内容：
1. FactorCalculator 从 parquet 加载因子
2. 策略声明 required_factors 后自动获取因子
3. 参数优化时因子共享
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd


def test_factor_calculator():
    """测试 FactorCalculator"""
    print("\n" + "=" * 60)
    print("测试 FactorCalculator")
    print("=" * 60)
    
    from core.strategies.utils.factor_calculator import (
        get_factor_calculator,
        get_available_factors,
        ALL_DB_FACTORS
    )
    
    # 查看可用因子
    available = get_available_factors()
    print(f"\n可用因子 ({len(available)}):")
    print(f"  数据库因子: {sorted(ALL_DB_FACTORS)}")
    
    # 创建测试数据
    calculator = get_factor_calculator()
    
    # 模拟交易日期和股票代码
    trading_dates = pd.date_range('2024-01-01', '2024-03-31', freq='B').strftime('%Y-%m-%d').tolist()
    stock_codes = ['000001.SZ', '000002.SZ', '600000.SH', '600519.SH']
    
    print(f"\n测试参数:")
    print(f"  日期范围: {trading_dates[0]} ~ {trading_dates[-1]}")
    print(f"  股票数量: {len(stock_codes)}")
    
    # 加载因子
    t0 = time.perf_counter()
    factors = calculator.load_factors(
        ['rsi_14', 'macd_dif', 'kdj_k', 'ma5', 'boll_upper'],
        trading_dates,
        stock_codes
    )
    t1 = time.perf_counter()
    
    print(f"\n加载结果 ({(t1-t0)*1000:.1f}ms):")
    for name, matrix in factors.items():
        valid_count = np.sum(~np.isnan(matrix))
        print(f"  {name}: 形状={matrix.shape}, 有效值={valid_count}")
    
    # 再次加载（测试缓存）
    t0 = time.perf_counter()
    factors2 = calculator.load_factors(['rsi_14', 'macd_dif'], trading_dates, stock_codes)
    t1 = time.perf_counter()
    print(f"\n缓存加载 ({(t1-t0)*1000:.1f}ms)")
    
    # 缓存统计
    stats = calculator.get_cache_stats()
    print(f"\n缓存统计:")
    print(f"  矩阵缓存: {stats['matrix_cache_size']}")


def test_declarative_strategy():
    """测试声明式因子策略"""
    print("\n" + "=" * 60)
    print("测试声明式因子策略")
    print("=" * 60)
    
    from core.strategies.vectorized_base import VectorizedStrategyBase
    
    class MyStrategy(VectorizedStrategyBase):
        required_factors = ['rsi_14', 'macd_dif', 'kdj_k', 'ma5']
        
        def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
            self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
            
            print(f"\n  策略内部因子状态:")
            print(f"    factors 字典: {list(self.factors.keys())}")
            
            # 使用因子
            rsi = self.factors.get('rsi_14')
            if rsi is not None:
                print(f"    rsi_14: 形状={rsi.shape}, 范围=[{np.nanmin(rsi):.1f}, {np.nanmax(rsi):.1f}]")
            
            # 也可以直接作为属性访问
            if hasattr(self, 'macd_dif') and self.macd_dif is not None:
                print(f"    macd_dif (属性): 形状={self.macd_dif.shape}")
            
            T, N = len(trading_dates), len(stock_codes)
            return np.zeros((T, N), dtype=np.int32)
    
    strategy = MyStrategy(name="test_declarative")
    
    print(f"\n策略声明的因子: {strategy.required_factors}")
    
    # 创建模拟数据
    T, N = 50, 100
    trading_dates = pd.date_range('2024-01-01', periods=T).strftime('%Y-%m-%d').tolist()
    stock_codes = [f'{i:06d}.SZ' for i in range(N)]
    
    np.random.seed(42)
    price_matrix = np.zeros((T, N, 4), dtype=np.float32)
    base_price = 10 + np.cumsum(np.random.randn(T, N) * 0.02, axis=0)
    price_matrix[:, :, 0] = base_price
    price_matrix[:, :, 1] = base_price + np.abs(np.random.randn(T, N) * 0.1)
    price_matrix[:, :, 2] = base_price - np.abs(np.random.randn(T, N) * 0.1)
    price_matrix[:, :, 3] = base_price
    
    # 创建 preloaded_data
    preloaded_data = {}
    for i, date in enumerate(trading_dates):
        df = pd.DataFrame({
            'trade_date': [date] * N,
            'stock_code': stock_codes,
            'open': price_matrix[i, :, 0],
            'high': price_matrix[i, :, 1],
            'low': price_matrix[i, :, 2],
            'close': price_matrix[i, :, 3],
            'volume': np.abs(np.random.randn(N) * 1e6),
            'amount': np.abs(np.random.randn(N) * 1e7),
        })
        preloaded_data[date] = df
    
    # 运行策略
    t0 = time.perf_counter()
    signals = strategy.generate_signals_vectorized(
        price_matrix=price_matrix,
        trading_dates=trading_dates,
        stock_codes=stock_codes,
        data_query=None,
        preloaded_data=preloaded_data
    )
    t1 = time.perf_counter()
    
    print(f"\n策略执行时间: {(t1-t0)*1000:.1f}ms")


def test_real_parquet_data():
    """测试真实 parquet 数据"""
    print("\n" + "=" * 60)
    print("测试真实 parquet 数据")
    print("=" * 60)
    
    from core.strategies.utils.factor_calculator import get_factor_calculator
    
    calculator = get_factor_calculator()
    
    # 从 parquet 中获取真实日期和股票代码
    import polars as pl
    hot_path = "data/parquet_data/factors_momentum_hot.parquet"
    
    if not os.path.exists(hot_path):
        print("parquet 文件不存在，跳过测试")
        return
    
    df = pl.read_parquet(hot_path)
    
    # 获取部分数据
    unique_dates = df.select('trade_date').unique().sort('trade_date').to_series().to_list()[:100]
    unique_codes = df.select('stock_code').unique().to_series().to_list()[:50]
    
    print(f"\n测试数据:")
    print(f"  日期范围: {unique_dates[0]} ~ {unique_dates[-1]}")
    print(f"  股票数量: {len(unique_codes)}")
    
    # 加载因子
    t0 = time.perf_counter()
    factors = calculator.load_factors(
        ['rsi_14', 'macd_dif', 'kdj_k', 'ma5', 'ma10', 'ma20', 'boll_upper', 'atr_14'],
        unique_dates,
        unique_codes
    )
    t1 = time.perf_counter()
    
    print(f"\n加载结果 ({(t1-t0)*1000:.1f}ms):")
    for name, matrix in factors.items():
        valid_count = np.sum(~np.isnan(matrix))
        valid_pct = valid_count / matrix.size * 100
        print(f"  {name:15s}: 形状={matrix.shape}, 有效值={valid_count} ({valid_pct:.1f}%)")


if __name__ == "__main__":
    test_factor_calculator()
    test_declarative_strategy()
    test_real_parquet_data()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
