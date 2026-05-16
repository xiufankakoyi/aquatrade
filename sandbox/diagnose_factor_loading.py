"""
诊断因子数据读取问题
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import cProfile
import pstats
import io
import time
from loguru import logger


def profile_factor_loading():
    """使用 cProfile 分析因子数据加载"""
    print("=" * 70)
    print("性能分析: 因子数据加载")
    print("=" * 70)
    
    # 创建 profiler
    profiler = cProfile.Profile()
    
    # 开始分析
    profiler.enable()
    
    start_time = time.time()
    
    from server.routes.screener_routes import get_factor_data_for_date
    
    factor_df = get_factor_data_for_date('2025-11-07')
    
    elapsed = time.time() - start_time
    
    profiler.disable()
    
    # 打印结果
    if factor_df is not None and not factor_df.is_empty():
        print(f"\n✅ 加载成功: {len(factor_df)} 行, 耗时: {elapsed:.2f}s")
        print(f"   列: {list(factor_df.columns)}")
        
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        for col in ma_cols:
            if col in factor_df.columns:
                null_count = factor_df[col].null_count()
                print(f"   {col}: null={null_count}/{len(factor_df)}")
            else:
                print(f"   {col}: 列不存在")
        
        # 显示样本数据
        print(f"\n   样本数据:")
        sample = factor_df.head(3)
        for row in sample.iter_rows(named=True):
            print(f"   {row.get('stock_code')}: ma5={row.get('ma5')}, ma10={row.get('ma10')}")
    else:
        print("❌ 加载失败")
    
    # 打印性能统计
    print("\n" + "=" * 70)
    print("性能统计 (Top 20)")
    print("=" * 70)
    
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)
    print(s.getvalue())


def check_arctic_factor_data():
    """检查 ArcticDB 中的因子数据"""
    print("\n" + "=" * 70)
    print("检查 ArcticDB factor 库数据")
    print("=" * 70)
    
    from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
    
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    
    symbols = lib.list_symbols()
    print(f"Symbol 数量: {len(symbols)}")
    
    # 检查第一个 symbol
    if symbols:
        symbol = symbols[0]
        print(f"\n检查 symbol: {symbol}")
        
        data = lib.read(symbol)
        df = data.data
        
        if hasattr(df, 'to_pandas'):
            df = df.to_pandas()
        
        print(f"  行数: {len(df)}")
        print(f"  列: {list(df.columns)}")
        
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        for col in ma_cols:
            if col in df.columns:
                null_count = df[col].isna().sum()
                print(f"  {col}: null={null_count}/{len(df)}")
            else:
                print(f"  {col}: 列不存在")


def check_parquet_factor_data():
    """检查 Parquet 中的因子数据"""
    print("\n" + "=" * 70)
    print("检查 Parquet 因子数据")
    print("=" * 70)
    
    import polars as pl
    
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    if not parquet_path.exists():
        print(f"❌ 文件不存在: {parquet_path}")
        return
    
    df = pl.scan_parquet(str(parquet_path))
    schema = df.collect_schema()
    
    print(f"列: {list(schema.keys())}")
    
    # 读取一行数据
    sample = df.head(1).collect()
    print(f"\n样本数据:")
    for col in sample.columns:
        print(f"  {col}: {sample[col][0]}")


if __name__ == '__main__':
    check_arctic_factor_data()
    check_parquet_factor_data()
    profile_factor_loading()
