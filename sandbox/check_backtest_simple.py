"""
检查回测结果 - 简洁版
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
print("回测结果")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    print(f"初始资金: {config.initial_capital:,.2f}")
    print(f"最终权益: {results['finalEquity']:,.2f}")
    print(f"总收益率: {results['totalReturn']:.2f}%")
    print(f"年化收益率: {results['annualizedReturn']:.2f}%")
    print(f"最大回撤: {abs(results['maxDrawdown']):.2f}%")
    print(f"夏普比率: {results['sharpeRatio']:.2f}")
    print(f"总交易数: {results['totalTrades']}")
    print(f"胜率: {results['winRate']:.2f}%")
    print(f"盈亏比: {results['profitFactor']:.2f}")
