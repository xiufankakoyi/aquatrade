"""
检查交易记录中的 cost 字段
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

data_manager = UnifiedDataManager()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=data_manager, config=config)
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

start_date = '2025-06-02'
end_date = '2025-06-10'

print("=" * 60)
print("检查交易记录中的 cost 字段")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    print(f"\n交易记录详情:")
    for t in trades:
        if t['action'] == 'buy':
            expected_cost = t['shares'] * t['price']
            actual_cost = t.get('cost', 0)
            commission = t.get('commission', 0)
            print(f"  {t['date']} BUY {t['code']}: {t['shares']}股 @ {t['price']:.2f}")
            print(f"    预期成本(不含佣金): {expected_cost:,.2f}")
            print(f"    实际 cost 字段: {actual_cost:,.2f}")
            print(f"    佣金: {commission:,.2f}")
            print(f"    总成本(含佣金): {expected_cost + commission:,.2f}")
            print()
