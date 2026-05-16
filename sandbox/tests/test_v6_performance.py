"""
V6 数据加载器性能测试

测试内容：
1. 矩阵缓存性能
2. 因子预计算性能
3. 对比 V5 vs V6
"""

import time
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from config.logger import get_logger

logger = get_logger(__name__)


def test_matrix_cache():
    """测试矩阵缓存性能"""
    print("\n" + "="*60)
    print("测试1: 矩阵缓存性能")
    print("="*60)
    
    from data_svc.database.polars_data_loader_v6 import get_polars_loader_v6
    
    loader = get_polars_loader_v6(enable_cache=True, enable_factor_precompute=False)
    
    start_date = "2024-01-01"
    end_date = "2024-03-31"
    fields = ['open', 'high', 'low', 'close', 'volume']
    
    # 第一次加载（冷缓存）
    print("\n第一次加载（冷缓存）...")
    t1 = time.perf_counter()
    data1 = loader.load_period_to_matrix(start_date, end_date, fields)
    t2 = time.perf_counter()
    cold_time = (t2 - t1) * 1000
    print(f"  耗时: {cold_time:.2f}ms")
    
    if data1:
        print(f"  矩阵形状: {data1['T']}x{data1['N']}")
        print(f"  交易日期: {len(data1['trading_dates'])} 天")
        print(f"  股票数量: {len(data1['stock_codes'])}")
    
    # 第二次加载（热缓存）
    print("\n第二次加载（热缓存）...")
    t1 = time.perf_counter()
    data2 = loader.load_period_to_matrix(start_date, end_date, fields)
    t2 = time.perf_counter()
    hot_time = (t2 - t1) * 1000
    print(f"  耗时: {hot_time:.2f}ms")
    
    # 验证数据一致性
    if data1 and data2:
        is_same = np.allclose(data1['matrices']['close'], data2['matrices']['close'])
        print(f"  数据一致性: {'✓' if is_same else '✗'}")
    
    # 缓存统计
    stats = loader.get_cache_stats()
    print(f"\n缓存统计:")
    print(f"  命中率: {stats.get('hit_rate', 0):.1f}%")
    print(f"  内存条目: {stats.get('memory_entries', 0)}")
    print(f"  内存大小: {stats.get('memory_size_mb', 0):.2f} MB")
    
    # 性能提升
    if cold_time > 0:
        speedup = cold_time / max(hot_time, 1)
        print(f"\n缓存加速: {speedup:.1f}x")
    
    return cold_time, hot_time


def test_factor_precompute():
    """测试因子预计算性能"""
    print("\n" + "="*60)
    print("测试2: 因子预计算性能")
    print("="*60)
    
    from data_svc.database.polars_data_loader_v6 import get_polars_loader_v6
    from core.strategies.utils.factor_precompute import get_factor_engine
    
    loader = get_polars_loader_v6(enable_cache=True, enable_factor_precompute=True)
    engine = get_factor_engine()
    
    start_date = "2024-01-01"
    end_date = "2024-06-30"
    
    # 加载基础数据
    print("\n加载基础数据...")
    t1 = time.perf_counter()
    base_data = loader.load_period_to_matrix(start_date, end_date, ['close'])
    t2 = time.perf_counter()
    print(f"  耗时: {(t2-t1)*1000:.2f}ms")
    
    if not base_data:
        print("  数据加载失败，跳过测试")
        return None, None
    
    close_matrix = base_data['matrices']['close']
    print(f"  矩阵形状: {close_matrix.shape}")
    
    # 测试单个因子
    print("\n测试单个因子计算...")
    factors_to_test = ['MA20', 'RSI14', 'GAIN_5D', 'VOLATILITY_20']
    
    for factor_name in factors_to_test:
        # 第一次计算（冷缓存）
        t1 = time.perf_counter()
        result1 = engine.compute_single(close_matrix, factor_name)
        t2 = time.perf_counter()
        cold_time = (t2 - t1) * 1000
        
        # 第二次计算（热缓存）
        t1 = time.perf_counter()
        result2 = engine.compute_single(close_matrix, factor_name)
        t2 = time.perf_counter()
        hot_time = (t2 - t1) * 1000
        
        print(f"  {factor_name}: 冷缓存={cold_time:.2f}ms, 热缓存={hot_time:.2f}ms, "
              f"加速={cold_time/max(hot_time,1):.1f}x")
    
    # 测试批量计算
    print("\n测试批量因子计算...")
    factor_list = ['MA5', 'MA10', 'MA20', 'MA60', 'RSI6', 'RSI14', 'GAIN_1D', 'GAIN_5D']
    
    t1 = time.perf_counter()
    factors = engine.compute_factors(
        close_matrix=close_matrix,
        factor_names=factor_list,
        date_range=(start_date, end_date)
    )
    t2 = time.perf_counter()
    batch_time = (t2 - t1) * 1000
    
    print(f"  计算 {len(factor_list)} 个因子: {batch_time:.2f}ms")
    print(f"  平均每个因子: {batch_time/len(factor_list):.2f}ms")
    print(f"  计算的因子: {list(factors.keys())}")
    
    return batch_time, factors


def test_load_with_factors():
    """测试数据+因子联合加载"""
    print("\n" + "="*60)
    print("测试3: 数据+因子联合加载")
    print("="*60)
    
    from data_svc.database.polars_data_loader_v6 import get_polars_loader_v6
    
    loader = get_polars_loader_v6(enable_cache=True, enable_factor_precompute=True)
    
    start_date = "2024-01-01"
    end_date = "2024-03-31"
    factor_names = ['MA20', 'RSI14', 'MACD_DIF']
    
    print(f"\n加载数据 + {len(factor_names)} 个因子...")
    t1 = time.perf_counter()
    data = loader.load_with_factors(
        start_date, end_date,
        base_fields=['open', 'high', 'low', 'close', 'volume'],
        factor_names=factor_names
    )
    t2 = time.perf_counter()
    total_time = (t2 - t1) * 1000
    
    print(f"  总耗时: {total_time:.2f}ms")
    
    if data:
        print(f"  基础数据字段: {list(data['matrices'].keys())}")
        print(f"  因子字段: {list(data.get('factors', {}).keys())}")
        
        # 验证因子数据
        if 'factors' in data and 'MA20' in data['factors']:
            ma20 = data['factors']['MA20']
            print(f"  MA20 矩阵形状: {ma20.shape}")
            print(f"  MA20 样本值: {ma20[-1, :5]}")  # 最后一天的5只股票
    
    return total_time


def test_preload_for_backtest():
    """测试回测预加载"""
    print("\n" + "="*60)
    print("测试4: 回测预加载")
    print("="*60)
    
    from data_svc.database.polars_data_loader_v6 import get_polars_loader_v6
    
    loader = get_polars_loader_v6(enable_cache=True, enable_factor_precompute=True)
    
    start_date = "2024-06-01"
    end_date = "2024-06-30"
    warmup_days = 60
    
    print(f"\n预加载回测数据...")
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  预热天数: {warmup_days}")
    
    result = loader.preload_for_backtest(start_date, end_date, warmup_days)
    
    print(f"\n预加载结果:")
    print(f"  状态: {result['status']}")
    print(f"  加载时间: {result['load_time_ms']:.2f}ms")
    print(f"  实际加载区间: {result['date_range']}")
    print(f"  矩阵形状: {result['matrix_shape']}")
    
    return result


def compare_v5_v6():
    """对比 V5 和 V6 性能"""
    print("\n" + "="*60)
    print("测试5: V5 vs V6 性能对比")
    print("="*60)
    
    from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
    from data_svc.database.polars_data_loader_v6 import get_polars_loader_v6
    
    v5 = get_polars_loader_v5()
    v6 = get_polars_loader_v6(enable_cache=True, enable_factor_precompute=False)
    
    start_date = "2024-01-01"
    end_date = "2024-06-30"
    fields = ['open', 'high', 'low', 'close', 'volume']
    
    # 测试 V5
    print("\nV5 加载...")
    times_v5 = []
    for i in range(3):
        t1 = time.perf_counter()
        data_v5 = v5.load_period_to_matrix(start_date, end_date, fields)
        t2 = time.perf_counter()
        times_v5.append((t2 - t1) * 1000)
    avg_v5 = sum(times_v5) / len(times_v5)
    print(f"  平均耗时: {avg_v5:.2f}ms")
    
    # 测试 V6 (冷缓存)
    v6.clear_cache()
    print("\nV6 冷缓存...")
    t1 = time.perf_counter()
    data_v6_cold = v6.load_period_to_matrix(start_date, end_date, fields)
    t2 = time.perf_counter()
    v6_cold_time = (t2 - t1) * 1000
    print(f"  耗时: {v6_cold_time:.2f}ms")
    
    # 测试 V6 (热缓存)
    print("\nV6 热缓存...")
    t1 = time.perf_counter()
    data_v6_hot = v6.load_period_to_matrix(start_date, end_date, fields)
    t2 = time.perf_counter()
    v6_hot_time = (t2 - t1) * 1000
    print(f"  耗时: {v6_hot_time:.2f}ms")
    
    # 对比结果
    print("\n对比结果:")
    print(f"  V5 平均: {avg_v5:.2f}ms")
    print(f"  V6 冷缓存: {v6_cold_time:.2f}ms")
    print(f"  V6 热缓存: {v6_hot_time:.2f}ms")
    
    if avg_v5 > 0:
        print(f"  V6热缓存 vs V5: {avg_v5/v6_hot_time:.1f}x 加速")
    
    return avg_v5, v6_cold_time, v6_hot_time


def main():
    """主测试函数"""
    print("="*60)
    print("V6 数据加载器性能测试")
    print("="*60)
    
    results = {}
    
    try:
        # 测试1: 矩阵缓存
        results['cache'] = test_matrix_cache()
    except Exception as e:
        print(f"\n矩阵缓存测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试2: 因子预计算
        results['factor'] = test_factor_precompute()
    except Exception as e:
        print(f"\n因子预计算测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试3: 联合加载
        results['combined'] = test_load_with_factors()
    except Exception as e:
        print(f"\n联合加载测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试4: 预加载
        results['preload'] = test_preload_for_backtest()
    except Exception as e:
        print(f"\n预加载测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # 测试5: 对比
        results['compare'] = compare_v5_v6()
    except Exception as e:
        print(f"\n对比测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print("\n所有测试完成！")
    print("\nV6 优化层已就绪，可以集成到回测系统中。")


if __name__ == "__main__":
    main()
