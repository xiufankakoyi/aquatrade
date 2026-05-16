"""
验证 API 迁移到 ArcticDB
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger


def test_benchmark_data_loading():
    """测试基准数据加载"""
    print("=" * 70)
    print("测试基准数据加载 (factor_precompute_service)")
    print("=" * 70)
    
    from data_svc.storage.factor_precompute_service import FactorPrecomputeService
    
    service = FactorPrecomputeService()
    bench_df = service._load_benchmark_data()
    
    if bench_df is not None:
        print(f"✅ 加载成功: {len(bench_df)} 行")
        print(f"   列: {bench_df.columns}")
        print(f"   日期范围: {bench_df['trade_date'].min()} ~ {bench_df['trade_date'].max()}")
    else:
        print("❌ 加载失败")


def test_factor_data_loading():
    """测试因子数据加载"""
    print("\n" + "=" * 70)
    print("测试因子数据加载 (screener_routes)")
    print("=" * 70)
    
    from server.routes.screener_routes import get_factor_data_for_date
    
    factor_df = get_factor_data_for_date('2025-11-07')
    
    if factor_df is not None and not factor_df.is_empty():
        print(f"✅ 加载成功: {len(factor_df)} 行")
        print(f"   列: {factor_df.columns[:5]}...")
    else:
        print("❌ 加载失败")


def test_index_kline_loading():
    """测试指数K线数据加载"""
    print("\n" + "=" * 70)
    print("测试指数K线数据加载 (visualization_api)")
    print("=" * 70)
    
    from server.visualization_api import BacktestVisualizationAPI
    
    api = BacktestVisualizationAPI()
    
    # 测试沪深300
    kline = api._get_index_kline_from_parquet('000300', '2025-10-01', '2025-11-07')
    
    if kline:
        print(f"✅ 沪深300 加载成功: {len(kline)} 条")
        print(f"   首条: {kline[0]}")
    else:
        print("❌ 沪深300 加载失败")


if __name__ == '__main__':
    test_benchmark_data_loading()
    test_factor_data_loading()
    test_index_kline_loading()
