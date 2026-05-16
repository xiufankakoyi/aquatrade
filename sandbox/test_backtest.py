import os
os.environ['DB_BACKEND'] = 'arcticdb'
import logging
logging.basicConfig(level=logging.INFO)

from data_svc.unified_data_manager import get_unified_manager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.trend_follow_v3 import TrendFollowStrategyV3, TrendFollowV3Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

mgr = get_unified_manager()
mgr.preload_to_memory(years=3)

data_query = OptimizedStockDataQuery()
engine = UnifiedBacktestEngine(data_query=data_query, config=BacktestConfig())

strategy = TrendFollowStrategyV3(config=TrendFollowV3Config())

# 用 2025 年数据测试
for event in engine.run_backtest_streaming(
    start_date='2025-06-02',
    end_date='2025-06-10',
    strategy=strategy
):
    if event.get('type') == 'trade':
        print('Trade:', event.get('data'))
    elif event.get('type') == 'final_metrics':
        result = event.get('data')
        print('Trades:', result.get('tradesCount'))
        print('Metrics:', result.get('metrics', {}).get('totalReturn', 'N/A'))
