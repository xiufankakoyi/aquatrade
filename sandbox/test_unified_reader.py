"""
UnifiedDataReader 测试脚本

测试功能：
1. 基础读取（单股票、多股票）
2. 分块缓存（股票+月份）
3. LRU 淘汰
4. 多进程读取
5. 预加载性能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time


def test_basic_read():
    """测试基础读取"""
    from data_svc.storage.unified_reader import UnifiedDataReader
    
    reader = UnifiedDataReader('stock_daily')
    reader.clear_cache()
    
    print("\n=== 测试基础读取 ===")
    
    df = reader.read('000001.SZ', '2024-01-01', '2024-01-31')
    print(f"单股票读取: {len(df)} 行")
    
    df = reader.read(['000001.SZ', '000002.SZ'], '2024-01-01', '2024-01-31')
    print(f"多股票读取: {len(df)} 行")
    
    symbols = reader.list_symbols()
    print(f"股票数量: {len(symbols)}")


def test_batch_cache():
    """测试分块缓存"""
    from data_svc.storage.unified_reader import UnifiedDataReader
    
    reader = UnifiedDataReader('stock_daily')
    reader.clear_cache()
    
    print("\n=== 测试分块缓存 ===")
    
    symbols = reader.list_symbols()[:100]
    
    start = time.time()
    df1 = reader.query('2024-01-01', '2024-01-31', symbols=symbols)
    t1 = time.time() - start
    print(f"首次查询: {t1*1000:.0f}ms, {len(df1)} 行, 缓存: {reader.get_cache_size_mb():.1f}MB")
    
    start = time.time()
    df2 = reader.query('2024-01-01', '2024-01-31', symbols=symbols)
    t2 = time.time() - start
    print(f"缓存命中: {t2*1000:.0f}ms, 提升: {t1/t2:.0f}x")
    
    assert len(df1) == len(df2), "数据不一致"


def test_lru_eviction():
    """测试 LRU 淘汰"""
    from data_svc.storage.unified_reader import UnifiedDataReader
    
    print("\n=== 测试 LRU 淘汰 ===")
    
    reader = UnifiedDataReader('stock_daily')
    reader.clear_cache()
    reader.set_cache_limit(10)
    
    symbols = reader.list_symbols()[:500]
    
    reader.query('2024-01-01', '2024-03-31', symbols=symbols)
    print(f"缓存大小: {reader.get_cache_size_mb():.1f}MB")
    print(f"缓存项数: {len(reader._memory_cache)}")
    
    reader.set_cache_limit(2048)
    reader.clear_cache()


def test_multiprocess():
    """测试多进程读取"""
    from data_svc.storage.unified_reader import UnifiedDataReader
    
    reader = UnifiedDataReader('stock_daily')
    reader.clear_cache()
    
    print("\n=== 测试多进程读取 ===")
    
    symbols = reader.list_symbols()[:1000]
    
    start = time.time()
    df1 = reader.read_batch(symbols, '2024-01-01', '2024-03-31')
    t1 = time.time() - start
    print(f"单进程: {t1*1000:.0f}ms, {len(df1)} 行")
    
    start = time.time()
    df2 = reader.read_batch_multiprocess(symbols, '2024-01-01', '2024-03-31', workers=4)
    t2 = time.time() - start
    print(f"多进程: {t2*1000:.0f}ms, {len(df2)} 行, 提升: {t1/t2:.1f}x")


def test_preload():
    """测试预加载性能"""
    from data_svc.storage.unified_reader import UnifiedDataReader
    
    reader = UnifiedDataReader('stock_daily')
    reader.clear_cache()
    
    print("\n=== 测试预加载 ===")
    
    for years in [1, 2]:
        reader.clear_cache()
        start = time.time()
        df = reader.preload_date_range('2024-01-01', f'{2024+years}-12-31')
        t = time.time() - start
        print(f"预加载 {years} 年: {t:.1f}s, {len(df)} 行, {reader.get_cache_size_mb():.0f}MB")


def main():
    print("UnifiedDataReader 测试")
    print("=" * 40)
    
    test_basic_read()
    test_batch_cache()
    test_lru_eviction()
    test_multiprocess()
    test_preload()
    
    print("\n" + "=" * 40)
    print("测试完成!")


if __name__ == '__main__':
    main()
