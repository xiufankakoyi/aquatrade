"""
检查信号和执行的代码匹配问题
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import numpy as np

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

# 预加载数据
query.preload_backtest_data('2025-06-01', '2025-06-30')
preloaded = getattr(query, '_preloaded_data', None)

if preloaded:
    # 获取交易日期和股票代码
    trading_dates = sorted(preloaded.keys())
    
    # 从 preloaded 获取股票代码
    all_codes_preloaded = set()
    for df in preloaded.values():
        if df is not None and len(df) > 0:
            all_codes_preloaded.update(df['stock_code'].unique().to_list())
    stock_codes_preloaded = sorted([str(c).zfill(6) for c in all_codes_preloaded])
    
    print(f"从 preloaded 获取的股票代码: {len(stock_codes_preloaded)}")
    print(f"前10个: {stock_codes_preloaded[:10]}")
    
    # 构建因子矩阵
    from core.backtest.factor_matrix import FactorMatrixBuilder
    builder = FactorMatrixBuilder()
    matrix = builder.build_from_preloaded(preloaded, use_cache=False)
    
    print(f"\n因子矩阵股票代码: {len(matrix.codes_str)}")
    print(f"前10个: {matrix.codes_str[:10]}")
    
    # 检查是否一致
    if stock_codes_preloaded == matrix.codes_str:
        print("\n✓ 股票代码一致")
    else:
        print("\n✗ 股票代码不一致!")
        # 找出差异
        set1 = set(stock_codes_preloaded)
        set2 = set(matrix.codes_str)
        print(f"  preloaded 独有的: {len(set1 - set2)}")
        print(f"  matrix 独有的: {len(set2 - set1)}")
        if set1 - set2:
            print(f"  示例: {list(set1 - set2)[:10]}")
        if set2 - set1:
            print(f"  示例: {list(set2 - set1)[:10]}")
