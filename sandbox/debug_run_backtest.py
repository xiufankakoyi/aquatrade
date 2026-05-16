"""
调试 run_backtest - 模拟完整的生成器流程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
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
strategy = MainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-03'
end_date = '2025-06-10'

print("=" * 60)
print(f"运行完整回测: {start_date} ~ {end_date}")
print("=" * 60)

event_count = 0
daily_equity_count = 0
trade_count = 0

# 收集所有事件
events = []
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    event_count += 1
    events.append(event)
    
    event_type = event.get('type')
    
    if event_type == 'backtest_start':
        print(f"\n[事件 {event_count}] 回测开始: {event['data']}")
    
    elif event_type == 'daily_equity_engine':
        daily_equity_count += 1
        data = event['data']
        print(f"\n[事件 {event_count}] 每日权益: {data['date']}, equity={data['equity']:.2f}, trades={data['trades']}")
    
    elif event_type == 'new_trade_engine':
        trade_count += 1
        t = event['data']
        print(f"\n[事件 {event_count}] 交易: {t['date']} {t['code']} {t['action']} {t['shares']}股 @ {t['price']:.2f}")
    
    elif event_type == 'progress':
        print(f"\n[事件 {event_count}] 进度: {event['data']['progress']}%")
    
    elif event_type == 'final_metrics':
        result = event['data']
        print(f"\n[事件 {event_count}] 最终指标:")
        print(f"  总交易数: {result.get('total_trades', 0)}")
        print(f"  胜率: {result.get('win_rate', 0):.2f}%")
        print(f"  总收益率: {result.get('total_return', 0):.2f}%")
    
    elif event_type == 'error':
        print(f"\n[事件 {event_count}] 错误: {event['data']}")

print(f"\n{'='*60}")
print("统计:")
print(f"  总事件数: {event_count}")
print(f"  每日权益事件数: {daily_equity_count}")
print(f"  交易事件数: {trade_count}")
print(f"{'='*60}")

# 检查事件类型分布
from collections import Counter
event_types = [e.get('type') for e in events]
print(f"\n事件类型分布:")
for t, c in Counter(event_types).most_common():
    print(f"  {t}: {c}")
