"""
调试更长时间的回测 - 验证卖出交易
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

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

# 使用更长的回测周期
start_date = '2025-01-01'
end_date = '2025-02-01'

print("=" * 60)
print(f"运行长时间回测: {start_date} ~ {end_date}")
print("=" * 60)

event_count = 0
daily_equity_count = 0
buy_count = 0
sell_count = 0

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    event_count += 1
    
    event_type = event.get('type')
    
    if event_type == 'backtest_start':
        print(f"\n[事件 {event_count}] 回测开始")
    
    elif event_type == 'new_trade_engine':
        t = event['data']
        if t['action'] == 'buy':
            buy_count += 1
        else:
            sell_count += 1
        if buy_count <= 10 or t['action'] == 'sell':  # 只打印前10个买入和所有卖出
            print(f"[事件 {event_count}] 交易: {t['date']} {t['code']} {t['action']} {t['shares']}股 @ {t['price']:.2f}")
    
    elif event_type == 'daily_equity_engine':
        daily_equity_count += 1
    
    elif event_type == 'final_metrics':
        data = event['data']
        print(f"\n{'='*60}")
        print("最终指标:")
        print(f"  tradesCount: {data.get('tradesCount', 0)}")
        print(f"  买入次数: {buy_count}")
        print(f"  卖出次数: {sell_count}")
        print(f"  winRate: {data.get('winRate', 0):.2f}%")
        print(f"  totalReturn: {data.get('totalReturn', 0):.2f}%")
        print(f"{'='*60}")

print(f"\n统计:")
print(f"  总事件数: {event_count}")
print(f"  每日权益事件数: {daily_equity_count}")
print(f"  买入次数: {buy_count}")
print(f"  卖出次数: {sell_count}")
