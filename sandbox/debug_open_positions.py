"""
检查最终持仓
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
print("检查最终持仓")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    # 构建持仓字典
    positions = {}
    for t in trades:
        code = t['code']
        if t['action'] == 'buy':
            if code not in positions:
                positions[code] = {'shares': 0, 'cost': 0}
            positions[code]['shares'] += t['shares']
            positions[code]['cost'] += t['cost']
        else:  # sell
            if code in positions:
                positions[code]['shares'] -= t['shares']
    
    # 找出未平仓的持仓
    open_positions = {k: v for k, v in positions.items() if v['shares'] > 0}
    
    print(f"\n未平仓持仓: {len(open_positions)} 只")
    total_open_cost = 0
    for code, pos in open_positions.items():
        print(f"  {code}: {pos['shares']}股, 成本={pos['cost']:,.2f}")
        total_open_cost += pos['cost']
    
    print(f"\n未平仓总成本: {total_open_cost:,.2f}")
    
    # 计算已实现盈亏
    buy_trades = [t for t in trades if t['action'] == 'buy']
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    buy_amount = sum(t['cost'] for t in buy_trades)
    sell_revenue = sum(t['revenue'] for t in sell_trades)
    commissions = sum(t['commission'] for t in trades)
    
    print(f"\n资金分析:")
    print(f"  初始资金: {config.initial_capital:,.2f}")
    print(f"  买入总成本: {buy_amount:,.2f}")
    print(f"  卖出总收入: {sell_revenue:,.2f}")
    print(f"  总佣金: {commissions:,.2f}")
    print(f"  未平仓成本: {total_open_cost:,.2f}")
    
    # 已实现盈亏 = 卖出收入 - 对应的买入成本
    # 简化计算：卖出收入 - (买入总成本 - 未平仓成本)
    realized_pnl = sell_revenue - (buy_amount - total_open_cost)
    print(f"\n已实现盈亏（估算）: {realized_pnl:,.2f}")
    
    # 最终权益 = 现金 + 持仓市值
    print(f"\n最终权益: {results['finalEquity']:,.2f}")
    print(f"总收益率: {results['totalReturn']:.2f}%")
