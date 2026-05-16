"""
检查卖出交易 amount 字段
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
print("检查卖出交易 amount 字段")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    # 检查卖出交易
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    print(f"\n卖出交易:")
    for t in sell_trades:
        shares = t['shares']
        price = t['price']
        expected_amount = shares * price
        actual_amount = t.get('amount', 0)
        commission = t.get('commission', 0)
        tax = t.get('tax', 0)
        revenue = t.get('revenue', 0)
        
        print(f"\n{t['date']} SELL {t['code']}:")
        print(f"  股数: {shares}")
        print(f"  价格: {price:.2f}")
        print(f"  预期金额(股数*价格): {expected_amount:,.2f}")
        print(f"  实际 amount 字段: {actual_amount:,.2f}")
        print(f"  佣金: {commission:.2f}")
        print(f"  税: {tax:.2f}")
        print(f"  revenue 字段: {revenue:,.2f}")
        print(f"  盈亏: {t['profit_loss']:,.2f}")
