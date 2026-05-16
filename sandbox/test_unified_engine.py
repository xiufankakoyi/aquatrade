"""
完整端到端回测测试
直接调用后端 API 验证数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings('ignore')

from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3, SimpleVolumeConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig


def test_unified_engine():
    """测试统一引擎"""
    print("=" * 80)
    print("统一引擎回测数据验证")
    print("=" * 80)
    
    # 初始化
    data_query = OptimizedStockDataQuery()
    config = BacktestConfig(initial_capital=1_000_000)
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy_config = SimpleVolumeConfig()
    strategy = SimpleVolumeStrategyV3(config=strategy_config)
    
    # 运行回测
    start_date = '2024-01-01'
    end_date = '2024-03-01'
    
    print(f"\n回测期间: {start_date} ~ {end_date}")
    print("-" * 80)
    
    final_data = None
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        t = update.get('type')
        if t == 'stream_complete':
            final_data = update.get('data', {})
            print(f"\n[stream_complete] 收到数据:")
            print(f"  finalEquity: {final_data.get('finalEquity')}")
            print(f"  totalReturn: {final_data.get('totalReturn')}")
            print(f"  maxDrawdown: {final_data.get('maxDrawdown')}")
            print(f"  sharpeRatio: {final_data.get('sharpeRatio')}")
            print(f"  calmarRatio: {final_data.get('calmarRatio')}")
            print(f"  benchmarkReturn: {final_data.get('benchmarkReturn')}")
            print(f"  equityCurve 点数: {len(final_data.get('equityCurve', []))}")
            print(f"  benchmarkCurve 点数: {len(final_data.get('benchmarkCurve', []))}")
            print(f"  monthlyReturns 数: {len(final_data.get('monthlyReturns', []))}")
            print(f"  trades 数: {len(final_data.get('trades', []))}")
            break
    
    if not final_data:
        print("ERROR: 没有收到 stream_complete 事件")
        return False
    
    # 验证
    print("\n" + "=" * 80)
    print("验证结果")
    print("=" * 80)
    
    issues = []
    
    if final_data.get('totalReturn') == 0:
        issues.append("totalReturn 为 0")
    
    if final_data.get('maxDrawdown') == 0:
        issues.append("maxDrawdown 为 0")
    
    if final_data.get('calmarRatio') == 0:
        issues.append("calmarRatio 为 0")
    
    if len(final_data.get('equityCurve', [])) == 0:
        issues.append("equityCurve 为空")
    
    if len(final_data.get('trades', [])) == 0:
        issues.append("trades 为空")
    
    if issues:
        print("[FAIL] 发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("[OK] 所有数据正常!")
        return True


if __name__ == "__main__":
    result = test_unified_engine()
    exit(0 if result else 1)
