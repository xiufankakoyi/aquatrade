"""
回测性能测试 - 验证优化效果
目标：一年回测 < 1000ms
"""
import time
import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.jq_volume_strategy_v2 import JQVolumeStrategypro, JQVolumeConfigpro


def test_backtest_performance():
    """测试回测性能"""
    print("=" * 60)
    print("回测性能测试")
    print("=" * 60)
    
    # 初始化数据查询
    print("\n[1/4] 初始化数据查询...")
    t0 = time.perf_counter()
    data_query = OptimizedStockDataQuery()
    print(f"      耗时: {(time.perf_counter() - t0)*1000:.1f}ms")
    
    # 创建策略
    print("\n[2/4] 创建策略...")
    t0 = time.perf_counter()
    config = JQVolumeConfigpro()
    strategy = JQVolumeStrategypro(config)
    print(f"      策略: {strategy.strategy_name}")
    print(f"      耗时: {(time.perf_counter() - t0)*1000:.1f}ms")
    
    # 设置回测参数 - 一年
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    print(f"\n[3/4] 回测参数:")
    print(f"      开始日期: {start_date}")
    print(f"      结束日期: {end_date}")
    
    # 获取交易日数量
    trading_dates = data_query.get_trading_dates(start_date, end_date)
    print(f"      交易日数: {len(trading_dates)}")
    
    # 创建回测引擎
    engine_config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        min_commission=5.0,
        warmup_days=30
    )
    engine = UnifiedBacktestEngine(data_query, engine_config)
    
    # 执行回测
    print("\n[4/4] 执行回测...")
    print("-" * 60)
    
    total_start = time.perf_counter()
    
    # 收集性能数据
    perf_data = {
        'data_load': [],
        'signal_generation': [],
        'execute_trades': [],
        'total_day': []
    }
    
    event_count = 0
    for event in engine.run_backtest(start_date, end_date, strategy):
        event_count += 1
        if event['type'] == 'daily_equity_engine':
            # 从引擎获取性能数据（通过日志或修改引擎返回性能数据）
            pass
        elif event['type'] == 'stream_complete':
            print("\n回测完成!")
            result = event['data']
            print(f"      总收益率: {result['totalReturn']:.2f}%")
            print(f"      交易次数: {result['totalTrades']}")
    
    total_elapsed = (time.perf_counter() - total_start) * 1000
    
    print("-" * 60)
    print(f"\n性能结果:")
    print(f"      总耗时: {total_elapsed:.1f}ms")
    print(f"      平均每日: {total_elapsed/len(trading_dates):.2f}ms")
    print(f"      事件数: {event_count}")
    
    # 判断是否达标
    target_ms = 1000
    if total_elapsed < target_ms:
        print(f"\n✅ 达标！({total_elapsed:.1f}ms < {target_ms}ms)")
    else:
        print(f"\n❌ 未达标！({total_elapsed:.1f}ms > {target_ms}ms)")
        print(f"   需要优化: {total_elapsed/target_ms:.1f}x")
    
    return total_elapsed


def test_simple_ma_strategy():
    """测试简单均线策略性能"""
    print("\n" + "=" * 60)
    print("简单均线策略性能测试")
    print("=" * 60)
    
    from core.strategies.vectorized_base import VectorizedStrategyBase
    from typing import Dict, List, Optional
    
    class SimpleMAStrategy(VectorizedStrategyBase):
        """简单均线策略 - 用于性能测试"""
        strategy_name = "SimpleMAStrategy"
        
        def __init__(self):
            super().__init__(name=self.strategy_name)
        
        def generate_signals_vectorized(
            self,
            price_matrix: np.ndarray,
            trading_dates: List[str],
            stock_codes: List[str],
            data_query,
            preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
        ) -> np.ndarray:
            """向量化信号生成 - 简单均线策略"""
            import time
            t_start = time.perf_counter()
            
            T, N = len(trading_dates), len(stock_codes)
            signal_matrix = np.zeros((T, N), dtype=np.int32)
            
            if preloaded_data is None or len(preloaded_data) == 0:
                return signal_matrix
            
            # 准备数据
            t0 = time.perf_counter()
            self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
            t_prepare = (time.perf_counter() - t0) * 1000
            
            # 简单策略：收盘价 > MA5 买入，< MA5 卖出
            close = self.close
            
            # 计算 MA5 - 使用更高效的向量化方法
            t0 = time.perf_counter()
            # 使用卷积计算移动平均（比循环快得多）
            from numpy.lib.stride_tricks import sliding_window_view
            
            # 对于每个股票，计算5日移动平均
            ma5 = np.full_like(close, np.nan)
            # 使用 pandas 的 rolling 方法（经过优化的C实现）
            close_df = pd.DataFrame(close)
            ma5 = close_df.rolling(window=5, min_periods=1).mean().values
            t_ma = (time.perf_counter() - t0) * 1000
            
            # 生成信号
            t0 = time.perf_counter()
            buy_condition = (close > ma5) & ~np.isnan(close) & ~np.isnan(ma5)
            sell_condition = (close < ma5) & ~np.isnan(close) & ~np.isnan(ma5)
            
            signal_matrix[buy_condition] = 1
            signal_matrix[sell_condition] = 2
            
            # T+1 逻辑
            signal_matrix[1:] = signal_matrix[:-1]
            signal_matrix[0] = 0
            t_signal = (time.perf_counter() - t0) * 1000
            
            t_total = (time.perf_counter() - t_start) * 1000
            print(f"[SimpleMAStrategy] 准备数据: {t_prepare:.1f}ms, MA计算: {t_ma:.1f}ms, 信号生成: {t_signal:.1f}ms, 总计: {t_total:.1f}ms")
            
            return signal_matrix
    
    # 初始化
    data_query = OptimizedStockDataQuery()
    strategy = SimpleMAStrategy()
    
    # 设置回测参数 - 5个月（根据用户日志）
    start_date = "2023-12-08"
    end_date = "2024-05-25"
    
    trading_dates = data_query.get_trading_dates(start_date, end_date)
    print(f"\n回测参数:")
    print(f"      开始日期: {start_date}")
    print(f"      结束日期: {end_date}")
    print(f"      交易日数: {len(trading_dates)}")
    
    engine_config = BacktestConfig(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        min_commission=5.0,
        warmup_days=30
    )
    engine = UnifiedBacktestEngine(data_query, engine_config)
    
    # 执行回测
    print("\n执行回测...")
    print("-" * 60)
    
    total_start = time.perf_counter()
    
    for event in engine.run_backtest(start_date, end_date, strategy):
        if event['type'] == 'stream_complete':
            print("\n回测完成!")
            result = event['data']
            print(f"      总收益率: {result['totalReturn']:.2f}%")
            print(f"      交易次数: {result['totalTrades']}")
    
    total_elapsed = (time.perf_counter() - total_start) * 1000
    
    print("-" * 60)
    print(f"\n性能结果:")
    print(f"      总耗时: {total_elapsed:.1f}ms ({total_elapsed/1000:.2f}s)")
    print(f"      平均每日: {total_elapsed/len(trading_dates):.2f}ms")
    
    # 打印缓存统计
    from core.strategies.vectorized_base import get_matrix_cache_stats
    cache_stats = get_matrix_cache_stats()
    print(f"\n缓存统计:")
    print(f"      命中: {cache_stats['hits']}")
    print(f"      未命中: {cache_stats['misses']}")
    print(f"      命中率: {cache_stats['hit_rate']:.1f}%")
    print(f"      缓存大小: {cache_stats['size']}")
    
    # 用户原来的性能：16.11秒
    print(f"\n对比:")
    print(f"      优化前: ~16110ms (根据日志)")
    print(f"      优化后: {total_elapsed:.1f}ms")
    if total_elapsed < 16110:
        print(f"      提升: {16110/total_elapsed:.1f}x")
    
    return total_elapsed


def profile_prepare_data():
    """详细分析 prepare_data 性能"""
    print("\n" + "=" * 60)
    print("prepare_data 性能分析")
    print("=" * 60)
    
    data_query = OptimizedStockDataQuery()
    
    # 预加载数据
    start_date = "2023-12-08"
    end_date = "2024-05-25"
    
    print(f"\n预加载数据: {start_date} 到 {end_date}")
    t0 = time.perf_counter()
    data_query.preload_backtest_data(start_date, end_date)
    preloaded = data_query._preloaded_data
    print(f"      耗时: {(time.perf_counter() - t0)*1000:.1f}ms")
    print(f"      数据点数: {len(preloaded)}")
    
    if preloaded:
        total_rows = sum(len(df) for df in preloaded.values() if df is not None)
        print(f"      总行数: {total_rows}")
        
        # 收集所有股票代码
        all_codes = set()
        for df in preloaded.values():
            if df is not None and not df.empty:
                all_codes.update(df['stock_code'].unique())
        trading_dates = sorted(preloaded.keys())
        stock_codes = sorted(list(all_codes))
        
        print(f"      交易日: {len(trading_dates)}")
        print(f"      股票数: {len(stock_codes)}")
        
        # 测试 prepare_data
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        strategy = VectorizedStrategyBase()
        
        print("\n测试 prepare_data...")
        t0 = time.perf_counter()
        strategy.prepare_data(preloaded, trading_dates, stock_codes)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"      耗时: {elapsed:.1f}ms")
        
        # 测试带 price_matrix 的情况
        print("\n测试带 price_matrix 的 prepare_data...")
        # 构建 price_matrix
        T, N = len(trading_dates), len(stock_codes)
        price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
        
        code_to_idx = {code: i for i, code in enumerate(stock_codes)}
        date_to_idx = {date: i for i, date in enumerate(trading_dates)}
        
        all_data_list = []
        for date_str, df_day in preloaded.items():
            if df_day is not None and not df.empty and date_str in date_to_idx:
                df_copy = df_day[['stock_code', 'open', 'high', 'low', 'close']].copy()
                df_copy['date_idx'] = date_to_idx[date_str]
                all_data_list.append(df_copy)
        
        if all_data_list:
            all_data_df = pd.concat(all_data_list, ignore_index=True)
            all_data_df['stock_code'] = all_data_df['stock_code'].astype(str).str.strip()
            all_data_df['code_idx'] = all_data_df['stock_code'].map(code_to_idx)
            all_data_df = all_data_df.dropna(subset=['code_idx'])
            
            if not all_data_df.empty:
                all_data_df['code_idx'] = all_data_df['code_idx'].astype(int)
                t_indices = all_data_df['date_idx'].values.astype(int)
                n_indices = all_data_df['code_idx'].values
                
                price_matrix[t_indices, n_indices, 0] = all_data_df['open'].values
                price_matrix[t_indices, n_indices, 1] = all_data_df['high'].values
                price_matrix[t_indices, n_indices, 2] = all_data_df['low'].values
                price_matrix[t_indices, n_indices, 3] = all_data_df['close'].values
        
        build_time = (time.perf_counter() - t0) * 1000
        print(f"      构建 price_matrix 耗时: {build_time:.1f}ms")
        
        # 现在测试带 price_matrix 的 prepare_data
        strategy2 = VectorizedStrategyBase()
        t0 = time.perf_counter()
        strategy2.prepare_data(preloaded, trading_dates, stock_codes, price_matrix)
        elapsed_with_matrix = (time.perf_counter() - t0) * 1000
        print(f"      带 price_matrix 的 prepare_data 耗时: {elapsed_with_matrix:.1f}ms")
        print(f"      节省: {elapsed - elapsed_with_matrix:.1f}ms ({(elapsed - elapsed_with_matrix)/elapsed*100:.1f}%)")


if __name__ == "__main__":
    # 运行性能分析
    profile_prepare_data()
    
    # 运行简单策略测试
    test_simple_ma_strategy()
    
    # 运行一年回测测试
    # test_backtest_performance()
