"""
检查买入卖出匹配
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
print("检查买入卖出匹配")
print("=" * 60)

results = None
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'stream_complete':
        results = event.get('data')
        break

if results:
    trades = results['trades']
    
    # 按股票代码统计
    stock_stats = {}
    for t in trades:
        code = t['code']
        if code not in stock_stats:
            stock_stats[code] = {'buy_shares': 0, 'sell_shares': 0, 'buy_cost': 0, 'sell_revenue': 0}
        
        if t['action'] == 'buy':
            stock_stats[code]['buy_shares'] += t['shares']
            stock_stats[code]['buy_cost'] += t['cost']
        else:
            stock_stats[code]['sell_shares'] += t['shares']
            stock_stats[code]['sell_revenue'] += t['revenue']
    
    # 找出不匹配的股票
    mismatched = {k: v for k, v in stock_stats.items() if v['buy_shares'] != v['sell_shares']}
    
    print(f"\n买入卖出不匹配的股票: {len(mismatched)} 只")
    
    total_open_cost = 0
    for code, stats in mismatched.items():
        open_shares = stats['buy_shares'] - stats['sell_shares']
        if open_shares > 0:
            # 估算未平仓成本
            avg_cost = stats['buy_cost'] / stats['buy_shares'] if stats['buy_shares'] > 0 else 0
            open_cost = open_shares * avg_cost
            total_open_cost += open_cost
            print(f"  {code}: 买入{stats['buy_shares']}股, 卖出{stats['sell_shares']}股, 未平仓{open_shares}股, 估算成本={open_cost:,.2f}")
    
    print(f"\n未平仓总成本（估算）: {total_open_cost:,.2f}")
    
    # 检查现金和持仓
    buy_trades = [t for t in trades if t['action'] == 'buy']
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    total_buy = sum(t['cost'] for t in buy_trades)
    total_sell = sum(t['revenue'] for t in sell_trades)
    total_commission = sum(t['commission'] for t in trades)
    
    print(f"\n资金统计:")
    print(f"  初始资金: {config.initial_capital:,.2f}")
    print(f"  总买入: {total_buy:,.2f}")
    print(f"  总卖出: {total_sell:,.2f}")
    print(f"  总佣金: {total_commission:,.2f}")
    
    # 现金 = 初始资金 - 总买入 + 总卖出 - 佣金
    expected_cash = config.initial_capital - total_buy + total_sell - total_commission
    print(f"  预期现金: {expected_cash:,.2f}")
    
    # 最终权益 = 现金 + 持仓市值
    print(f"\n最终权益: {results['finalEquity']:,.2f}")
