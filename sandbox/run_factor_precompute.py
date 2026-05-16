"""
运行因子预计算服务补全所有数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from data_svc.storage.factor_precompute_service import FactorPrecomputeService
from loguru import logger


def run_precompute():
    """运行因子预计算"""
    print("=" * 70)
    print("因子预计算服务 - 补全 2024-2026 年数据")
    print("=" * 70)
    
    service = FactorPrecomputeService()
    
    # 从 2024-01-01 开始计算
    result = service.precompute_all_factors(
        start_date='2024-01-01',
        end_date=None,  # 到最新日期
        batch_days=30
    )
    
    print(f"\n计算结果:")
    print(f"  成功: {result.success}")
    print(f"  记录数: {result.records_computed}")
    print(f"  消息: {result.message}")
    if result.error:
        print(f"  错误: {result.error}")


if __name__ == '__main__':
    run_precompute()
