"""
测试智能因子加载器性能

测试内容：
1. 数据库因子加载（ma5, ma10, ma20）
2. 计算型因子（rsi_14, macd_dif, kdj_k）
3. 性能对比
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd


def test_smart_factor_loader():
    """测试智能因子加载器"""
    print("\n" + "=" * 60)
    print("测试智能因子加载器")
    print("=" * 60)
    
    from core.strategies.utils.smart_factor_loader import (
        get_smart_factor_loader, 
        DB_AVAILABLE_FACTORS, 
        COMPUTE_FACTORS
    )
    
    print(f"\n数据库可用因子 ({len(DB_AVAILABLE_FACTORS)}):")
    print(f"  {sorted(DB_AVAILABLE_FACTORS)[:15]}...")
    
    print(f"\n计算型因子 ({len(COMPUTE_FACTORS)}):")
    print(f"  {list(COMPUTE_FACTORS.keys())}")
    
    # 创建模拟数据
    T, N = 250, 1000  # 250天, 1000只股票
    print(f"\n模拟数据: T={T}, N={N}")
    
    np.random.seed(42)
    close = 10 + np.cumsum(np.random.randn(T, N) * 0.02, axis=0).astype(np.float32)
    high = close + np.abs(np.random.randn(T, N) * 0.1).astype(np.float32)
    low = close - np.abs(np.random.randn(T, N) * 0.1).astype(np.float32)
    volume = np.abs(np.random.randn(T, N) * 1e6).astype(np.float32)
    
    # 初始化加载器
    loader = get_smart_factor_loader()
    loader.clear_cache()
    
    # 模拟策略数据
    strategy_id = id(loader)
    strategy_data = {
        'close': close,
        'high': high,
        'low': low,
        'volume': volume,
        'ma5': None,  # 模拟数据库没有
        'ma10': None,
        'ma20': None,
    }
    loader.register_strategy_data(strategy_id, strategy_data)
    
    # 测试计算型因子
    print("\n--- 测试计算型因子 ---")
    test_factors = ['rsi_14', 'macd_dif', 'kdj_k', 'boll_upper', 'atr_14', 'gain_5d']
    
    for factor_name in test_factors:
        # 首次计算
        t0 = time.perf_counter()
        result = loader.get_factor(factor_name, strategy_id)
        t1 = time.perf_counter()
        first_time = (t1 - t0) * 1000
        
        if result is not None:
            # 缓存命中
            t0 = time.perf_counter()
            result2 = loader.get_factor(factor_name, strategy_id)
            t1 = time.perf_counter()
            cache_time = (t1 - t0) * 1000
            
            print(f"  {factor_name}: 首次={first_time:.2f}ms, 缓存={cache_time:.3f}ms, "
                  f"形状={result.shape}, 有效值={np.sum(~np.isnan(result))}")
        else:
            print(f"  {factor_name}: 计算失败")
    
    # 测试批量获取
    print("\n--- 测试批量获取 ---")
    t0 = time.perf_counter()
    batch_results = loader.batch_get_factors(['rsi_14', 'macd_dif', 'kdj_k', 'gain_5d'], strategy_id)
    t1 = time.perf_counter()
    print(f"  批量获取4个因子: {(t1-t0)*1000:.2f}ms")
    print(f"  获取结果: {list(batch_results.keys())}")


def test_vectorized_base_integration():
    """测试与 VectorizedStrategyBase 的集成"""
    print("\n" + "=" * 60)
    print("测试 VectorizedStrategyBase 集成")
    print("=" * 60)
    
    from core.strategies.vectorized_base import VectorizedStrategyBase
    
    # 创建策略实例
    class TestStrategy(VectorizedStrategyBase):
        def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
            self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
            
            # 测试获取因子
            print("\n  测试 get_factor 方法:")
            
            # 数据库因子
            ma5 = self.get_factor('ma5')
            print(f"    ma5: {ma5 is not None}, 形状={ma5.shape if ma5 is not None else None}")
            
            # 计算型因子
            rsi = self.get_factor('rsi_14')
            print(f"    rsi_14: {rsi is not None}, 形状={rsi.shape if rsi is not None else None}")
            
            macd = self.get_factor('macd_dif')
            print(f"    macd_dif: {macd is not None}, 形状={macd.shape if macd is not None else None}")
            
            kdj = self.get_factor('kdj_k')
            print(f"    kdj_k: {kdj is not None}, 形状={kdj.shape if kdj is not None else None}")
            
            # 返回空信号
            T, N = len(trading_dates), len(stock_codes)
            return np.zeros((T, N), dtype=np.int32)
    
    strategy = TestStrategy(name="test_factor_strategy")
    
    # 创建模拟数据
    T, N = 100, 500
    trading_dates = pd.date_range('2024-01-01', periods=T).strftime('%Y-%m-%d').tolist()
    stock_codes = [f'{i:06d}.SZ' for i in range(N)]
    
    np.random.seed(42)
    price_matrix = np.zeros((T, N, 4), dtype=np.float32)
    base_price = 10 + np.cumsum(np.random.randn(T, N) * 0.02, axis=0)
    price_matrix[:, :, 0] = base_price  # open
    price_matrix[:, :, 1] = base_price + np.abs(np.random.randn(T, N) * 0.1)  # high
    price_matrix[:, :, 2] = base_price - np.abs(np.random.randn(T, N) * 0.1)  # low
    price_matrix[:, :, 3] = base_price  # close
    
    # 创建 preloaded_data
    preloaded_data = {}
    for i, date in enumerate(trading_dates):
        df = pd.DataFrame({
            'trade_date': [date] * N,  # 添加 trade_date 列
            'stock_code': stock_codes,
            'open': price_matrix[i, :, 0],
            'high': price_matrix[i, :, 1],
            'low': price_matrix[i, :, 2],
            'close': price_matrix[i, :, 3],
            'volume': np.abs(np.random.randn(N) * 1e6),
            'amount': np.abs(np.random.randn(N) * 1e7),
            'total_mv': np.abs(np.random.randn(N) * 1e10),
            'turnover_rate': np.abs(np.random.randn(N) * 5),
            'volume_ratio': 0.5 + np.random.rand(N),
            'ma5': base_price[i] * (1 + np.random.randn(N) * 0.01),  # 模拟数据库有 ma5
            'ma10': base_price[i] * (1 + np.random.randn(N) * 0.01),
            'ma20': base_price[i] * (1 + np.random.randn(N) * 0.01),
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
    
    print(f"\n  策略执行时间: {(t1-t0)*1000:.2f}ms")
    print(f"  信号形状: {signals.shape}")


def test_performance_comparison():
    """性能对比测试"""
    print("\n" + "=" * 60)
    print("性能对比测试")
    print("=" * 60)
    
    from core.strategies.utils.smart_factor_loader import get_smart_factor_loader
    
    # 大规模数据
    T, N = 500, 2000  # 500天, 2000只股票
    print(f"\n数据规模: T={T}, N={N}")
    
    np.random.seed(42)
    close = 10 + np.cumsum(np.random.randn(T, N) * 0.02, axis=0).astype(np.float32)
    high = close + np.abs(np.random.randn(T, N) * 0.1).astype(np.float32)
    low = close - np.abs(np.random.randn(T, N) * 0.1).astype(np.float32)
    
    loader = get_smart_factor_loader()
    loader.clear_cache()
    
    strategy_id = id(loader)
    loader.register_strategy_data(strategy_id, {
        'close': close,
        'high': high,
        'low': low,
    })
    
    # 测试各因子计算时间
    factors_to_test = ['rsi_14', 'macd_dif', 'kdj_k', 'atr_14', 'boll_upper', 'gain_5d', 'volatility_20']
    
    print("\n因子计算时间:")
    for factor_name in factors_to_test:
        loader.clear_cache()
        t0 = time.perf_counter()
        result = loader.get_factor(factor_name, strategy_id)
        t1 = time.perf_counter()
        
        if result is not None:
            print(f"  {factor_name:15s}: {(t1-t0)*1000:8.2f}ms")


if __name__ == "__main__":
    test_smart_factor_loader()
    test_vectorized_base_integration()
    test_performance_comparison()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
