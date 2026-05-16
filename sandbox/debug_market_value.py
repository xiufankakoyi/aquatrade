"""
检查未平仓股票的市值
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
print("检查未平仓股票的市值")
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
    
    # 获取最后一天的收盘价
    last_date = '2025-11-19'
    prices = {}
    for t in trades:
        if t['date'] == last_date or t['date'] == '2025-11-18':
            code = t['code']
            prices[code] = t['price']
    
    # 计算未平仓市值
    print(f"\n未平仓股票市值（假设最后一天收盘价）:")
    total_market_value = 0
    for code, stats in stock_stats.items():
        open_shares = stats['buy_shares'] - stats['sell_shares']
        if open_shares > 0:
            # 从交易记录中找最后的价格
            last_price = None
            for t in reversed(trades):
                if t['code'] == code:
                    last_price = t['price']
                    break
            
            if last_price:
                market_value = open_shares * last_price
                total_market_value += market_value
                avg_cost = stats['buy_cost'] / stats['buy_shares']
                pnl = market_value - open_shares * avg_cost
                print(f"  {code}: {open_shares}股 @ {last_price:.2f} = {market_value:,.2f} (成本={open_shares * avg_cost:,.2f}, 浮盈={pnl:,.2f})")
    
    print(f"\n未平仓总市值: {total_market_value:,.2f}")
    
    # 资金统计
    buy_trades = [t for t in trades if t['action'] == 'buy']
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    total_buy = sum(t['cost'] for t in buy_trades)
    total_sell = sum(t['revenue'] for t in sell_trades)
    total_commission = sum(t['commission'] for t in trades)
    
    expected_cash = config.initial_capital - total_buy + total_sell - total_commission
    expected_equity = expected_cash + total_market_value
    
    print(f"\n资金核对:")
    print(f"  预期现金: {expected_cash:,.2f}")
    print(f"  未平仓市值: {total_market_value:,.2f}")
    print(f"  预期权益: {expected_equity:,.2f}")
    print(f"  实际权益: {results['finalEquity']:,.2f}")
    print(f"  差额: {expected_equity - results['finalEquity']:,.2f}")
