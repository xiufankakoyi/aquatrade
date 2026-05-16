"""
检查同一股票的买入记录
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
end_date = '2025-11-19'

print("=" * 60)
print("检查同一股票的买入记录")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    # 按股票代码分组买入交易
    buy_by_code = {}
    for t in trades:
        if t['action'] == 'buy':
            code = t['code']
            if code not in buy_by_code:
                buy_by_code[code] = []
            buy_by_code[code].append(t)
    
    # 找出多次买入的股票
    multi_buy = {k: v for k, v in buy_by_code.items() if len(v) > 1}
    
    print(f"\n多次买入的股票: {len(multi_buy)} 只")
    for code, buys in list(multi_buy.items())[:5]:
        print(f"\n{code}:")
        total_cost = 0
        total_shares = 0
        for b in buys:
            print(f"  {b['date']}: {b['shares']}股 @ {b['price']:.2f}, cost={b['cost']:,.2f}")
            total_cost += b['cost']
            total_shares += b['shares']
        print(f"  总计: {total_shares}股, 总成本={total_cost:,.2f}")
