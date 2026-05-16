"""
调试策略执行流程
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.trend_follow_v2 import TrendFollowStrategyV2
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def debug_strategy():
    print("=" * 80)
    print("调试策略执行")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    strategy = TrendFollowStrategyV2()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n测试区间: {start_date} ~ {end_date}")
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'daily_equity_engine':
            print(f"  {data.get('date')}: equity={data.get('equity')}, positions={data.get('positions')}")
        elif update_type in ('new_trade', 'new_trade_engine'):
            print(f"  交易: {data}")


if __name__ == "__main__":
    debug_strategy()
