"""
检查卖出交易的价格
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
print("检查卖出交易的价格")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'new_trade_engine':
        trade = event['data']
        if trade['action'] == 'sell':
            print(f"\n{trade['date']} SELL {trade['code']}:")
            print(f"  股数: {trade['shares']}")
            print(f"  价格: {trade['price']:.2f}")
            print(f"  金额: {trade['revenue']:,.2f}")
            print(f"  佣金: {trade['commission']:.2f}")
            print(f"  盈亏: {trade['profit_loss']:,.2f}")
            print(f"  ROI: {trade['roi']:.2f}%")
    elif event.get('type') == 'stream_complete':
        results = event.get('data')
        break
