"""
调试交易执行过程 - 为什么有信号但没有交易
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import pandas as pd

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

print("=" * 60)
print("调试交易执行过程")
print("=" * 60)

start_date = '2025-01-02'
end_date = '2025-01-05'

print(f"\n回测范围: {start_date} ~ {end_date}")
print(f"初始资金: {config.initial_capital:,.0f}")
print(f"仓位比例: {config.position_ratio}")
print(f"最大持仓: {config.max_positions}")

event_count = 0
signals_by_date = {}
trades_by_date = {}

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    event_count += 1
    event_type = event.get('type')
    
    if event_type == 'backtest_start':
        print(f"\n[事件 {event_count}] 回测开始")
        print(f"  交易日: {event['data'].get('trading_dates', [])}")
    
    elif event_type == 'new_trade_engine':
        t = event['data']
        date = t['date']
        if date not in trades_by_date:
            trades_by_date[date] = []
        trades_by_date[date].append(t)
        if event_count <= 20:  # 只打印前20个交易
            print(f"[事件 {event_count}] 交易: {date} {t['code']} {t['action']} {t['shares']}股 @ {t['price']:.2f}")
    
    elif event_type == 'daily_equity_engine':
        d = event['data']
        if d['date'] not in signals_by_date:
            signals_by_date[d['date']] = d
    
    elif event_type == 'final_metrics':
        print(f"\n[事件 {event_count}] 最终指标")
        data = event['data']
        print(f"  tradesCount: {data.get('tradesCount', 0)}")
        print(f"  totalReturn: {data.get('totalReturn', 0):.2f}%")

print(f"\n" + "=" * 60)
print("每日统计")
print("=" * 60)

all_dates = sorted(set(list(signals_by_date.keys()) + list(trades_by_date.keys())))
for date in all_dates:
    signal_info = signals_by_date.get(date, {})
    trades = trades_by_date.get(date, [])
    buy_count = sum(1 for t in trades if t['action'] == 'buy')
    sell_count = sum(1 for t in trades if t['action'] == 'sell')
    
    print(f"\n{date}:")
    print(f"  权益: {signal_info.get('total_equity', 0):,.0f}")
    print(f"  持仓: {signal_info.get('position_count', 0)} 只")
    print(f"  交易: 买入 {buy_count}, 卖出 {sell_count}")

print(f"\n" + "=" * 60)
print("分析")
print("=" * 60)

# 检查2025-01-02的情况
jan2_key = '20250102'
if jan2_key in trades_by_date:
    print(f"\n2025-01-02有 {len(trades_by_date[jan2_key])} 笔交易")
else:
    print(f"\n2025-01-02没有交易")
    print(f"\n可能原因:")
    print(f"1. 虽然有217个买入信号，但可能都被过滤了")
    print(f"2. 涨跌停限制")
    print(f"3. 资金不足")
    print(f"4. 持仓限制")
    print(f"5. 交易执行逻辑中的其他过滤条件")

total_buys = sum(sum(1 for t in trades if t['action'] == 'buy') for trades in trades_by_date.values())
total_sells = sum(sum(1 for t in trades if t['action'] == 'sell') for trades in trades_by_date.values())

print(f"\n总计:")
print(f"  买入: {total_buys}")
print(f"  卖出: {total_sells}")
