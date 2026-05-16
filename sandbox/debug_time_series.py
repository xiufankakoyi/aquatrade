"""
调试时间序列
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
import pandas as pd

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)

start_date = '2025-06-03'
end_date = '2025-06-10'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

print(f"start_ts: {start_ts}")
print(f"end_ts: {end_ts}")

# 获取交易日
try:
    trading_dates = query.get_trading_dates(start_date, end_date)
    print(f"\n交易日数量: {len(trading_dates)}")
    print(f"交易日: {trading_dates}")
except Exception as e:
    print(f"获取交易日失败: {e}")
    import traceback
    traceback.print_exc()

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
print(f"\n时间序列数量: {len(time_series)}")
print(f"时间序列: {[t.strftime('%Y-%m-%d') for t in time_series]}")
