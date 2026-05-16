"""
检查交易详情
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

query = OptimizedStockDataQuery()

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

# 收集所有事件
trades = []
equity_history = []

for event in engine.run_backtest(strategy=strategy, start_date='2025-06-01', end_date='2025-11-19'):
    if event.get('type') == 'new_trade_engine':
        trades.append(event['data'])
    elif event.get('type') == 'daily_equity_engine':
        equity_history.append(event['data'])
    elif event.get('type') == 'stream_complete':
        result = event['data']
        break

print(f"总交易数: {len(trades)}")
print(f"\n前10笔交易:")
for i, t in enumerate(trades[:10]):
    pnl = t.get('pnl', 0)
    pnl_pct = t.get('pnl_pct', 0)
    print(f"  {i+1}. {t['date']} {t['code']} {t['direction']} 价:{t['price']:.2f} 量:{t['volume']} PnL:{pnl:.2f} ({pnl_pct:.2f}%)")

# 计算胜率
if trades:
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
    
    win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
    avg_win = sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    print(f"\n交易统计:")
    print(f"  胜率: {win_rate:.1f}%")
    print(f"  盈利交易: {len(winning_trades)} 笔")
    print(f"  亏损交易: {len(losing_trades)} 笔")
    if avg_loss != 0:
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        print(f"  盈亏比: {profit_factor:.2f}")

# 检查持仓情况
print(f"\n最后5天持仓:")
for e in equity_history[-5:]:
    print(f"  {e['date']}: 权益={e['equity']:,.2f}, 现金={e['cash']:,.2f}, 持仓数={e['positions']}")
