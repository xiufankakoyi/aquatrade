"""
检查长期回测的权益变化
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

start_date = '2024-01-02'
end_date = '2026-1-19'

print("=" * 60)
print("检查长期回测的权益变化")
print("=" * 60)

equity_history = []
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    if event.get('type') == 'daily_equity_engine':
        data = event['data']
        equity_history.append({
            'date': data['date'],
            'equity': data['equity'],
            'cash': data['cash'],
            'positions': data['positions']
        })
    elif event.get('type') == 'stream_complete':
        break

# 显示权益曲线的关键点
print(f"\n权益曲线关键点:")
print(f"  起始: {equity_history[0]['date']} 权益={equity_history[0]['equity']:,.2f}")

# 找到最高点和最低点
max_equity = max(equity_history, key=lambda x: x['equity'])
min_equity = min(equity_history, key=lambda x: x['equity'])
final_equity = equity_history[-1]

print(f"  最高: {max_equity['date']} 权益={max_equity['equity']:,.2f}")
print(f"  最低: {min_equity['date']} 权益={min_equity['equity']:,.2f}")
print(f"  结束: {final_equity['date']} 权益={final_equity['equity']:,.2f}")

# 检查最后几天的数据
print(f"\n最后5天:")
for e in equity_history[-5:]:
    print(f"  {e['date']}: 权益={e['equity']:,.2f}, 现金={e['cash']:,.2f}, 持仓={e['positions']}")

# 检查权益变化幅度
changes = []
for i in range(1, len(equity_history)):
    prev = equity_history[i-1]['equity']
    curr = equity_history[i]['equity']
    change_pct = (curr - prev) / prev * 100
    changes.append(change_pct)

print(f"\n日收益率统计:")
print(f"  最大涨幅: {max(changes):.2f}%")
print(f"  最大跌幅: {min(changes):.2f}%")
print(f"  平均日收益: {sum(changes)/len(changes):.4f}%")

# 找出跌幅最大的日子
max_drop_idx = changes.index(min(changes))
print(f"\n最大跌幅日: {equity_history[max_drop_idx+1]['date']}")
print(f"  前一天权益: {equity_history[max_drop_idx]['equity']:,.2f}")
print(f"  当天权益: {equity_history[max_drop_idx+1]['equity']:,.2f}")
print(f"  前一天持仓: {equity_history[max_drop_idx]['positions']}")
print(f"  当天持仓: {equity_history[max_drop_idx+1]['positions']}")
