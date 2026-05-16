"""
运行正确的回测（使用实际数据范围）
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

# 使用 OptimizedStockDataQuery
query = OptimizedStockDataQuery()

# 获取交易日期
dates = query.get_trading_dates()
print(f"数据范围: {dates[0]} ~ {dates[-1]}")

# 使用 2025 年的数据
start_date = '2025-06-01'
end_date = '2025-11-19'

print(f"\n回测区间: {start_date} ~ {end_date}")
print("=" * 60)

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

# 运行回测
equity_history = []
trade_count = 0
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        equity_history.append({
            'date': data['date'],
            'equity': data['equity'],
            'cash': data['cash'],
            'positions': data['positions']
        })
    elif event.get('type') == 'new_trade_engine':
        trade_count += 1
    elif event.get('type') == 'stream_complete':
        break

if equity_history:
    print(f"\n权益曲线:")
    print(f"  起始: {equity_history[0]['date']} 权益={equity_history[0]['equity']:,.2f}")
    
    max_equity = max(equity_history, key=lambda x: x['equity'])
    min_equity = min(equity_history, key=lambda x: x['equity'])
    final_equity = equity_history[-1]
    
    print(f"  最高: {max_equity['date']} 权益={max_equity['equity']:,.2f}")
    print(f"  最低: {min_equity['date']} 权益={min_equity['equity']:,.2f}")
    print(f"  结束: {final_equity['date']} 权益={final_equity['equity']:,.2f}")
    
    # 计算收益率
    total_return = (final_equity['equity'] - equity_history[0]['equity']) / equity_history[0]['equity'] * 100
    print(f"\n总收益率: {total_return:.2f}%")
    
    # 计算最大回撤
    peak = equity_history[0]['equity']
    max_drawdown = 0
    max_dd_date = None
    for e in equity_history:
        if e['equity'] > peak:
            peak = e['equity']
        drawdown = (peak - e['equity']) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_dd_date = e['date']
    
    print(f"最大回撤: {max_drawdown:.2f}% (发生在 {max_dd_date})")
    print(f"总交易数: {trade_count}")
    
    # 检查日收益率
    print(f"\n日收益率统计:")
    daily_returns = []
    for i in range(1, len(equity_history)):
        ret = (equity_history[i]['equity'] - equity_history[i-1]['equity']) / equity_history[i-1]['equity'] * 100
        daily_returns.append(ret)
    
    if daily_returns:
        print(f"  最大涨幅: {max(daily_returns):.2f}%")
        print(f"  最大跌幅: {min(daily_returns):.2f}%")
        print(f"  平均日收益: {sum(daily_returns)/len(daily_returns):.4f}%")
else:
    print("没有权益数据")
