"""
检查数据范围和回测详细情况
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

data_manager = UnifiedDataManager()

# 获取交易日期
dates = data_manager.get_trading_dates()
print(f"数据范围: {dates[0] if dates else 'N/A'} 到 {dates[-1] if dates else 'N/A'}")

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

# 使用实际数据范围
start_date = dates[0] if dates else '2024-01-02'
end_date = dates[-1] if dates else '2024-12-31'

print(f"\n回测区间: {start_date} 到 {end_date}")
print("=" * 60)

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
    
    # 计算最大回撤
    peak = equity_history[0]['equity']
    max_drawdown = 0
    for e in equity_history:
        if e['equity'] > peak:
            peak = e['equity']
        drawdown = (peak - e['equity']) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    print(f"\n最大回撤: {max_drawdown:.2f}%")
    print(f"总交易数: {trade_count}")
    
    # 检查持仓情况
    print(f"\n最后5天持仓:")
    for e in equity_history[-5:]:
        print(f"  {e['date']}: 权益={e['equity']:,.2f}, 现金={e['cash']:,.2f}, 持仓数={e['positions']}")
else:
    print("没有权益数据")
