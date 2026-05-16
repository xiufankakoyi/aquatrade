"""
调试流式回测
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import pandas as pd
from data_svc.unified_data_manager import UnifiedDataManager
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

# 创建数据管理器
data_manager = UnifiedDataManager()

# 创建回测配置
config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

# 创建回测引擎
engine = UnifiedBacktestEngine(
    data_query=data_manager,
    config=config
)

# 创建策略
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

# 设置回测区间
start_date = '2024-01-02'
end_date = '2024-01-10'

print("=" * 80)
print("调试流式回测")
print("=" * 80)

results = []
trades = []
event_count = {'daily_equity_engine': 0, 'new_trade_engine': 0, 'other': 0}

start_time = time.time()

for i, event in enumerate(engine.run_backtest_streaming(start_date, end_date, strategy)):
    event_type = event.get('type')
    data = event.get('data', {})
    
    if event_type == 'daily_equity_engine':
        event_count['daily_equity_engine'] += 1
        results.append({
            'date': data.get('date'),
            'equity': data.get('equity', 0),
            'cash': data.get('cash', 0),
            'positions': data.get('positions', 0),
            'trades': data.get('trades', 0)
        })
        
        # 只打印前3天和最后1天
        if i < 3 or event_count['daily_equity_engine'] == 7:
            print(f"\n[{data.get('date')}] 权益: {data.get('equity', 0):,.2f} | "
                  f"现金: {data.get('cash', 0):,.2f} | "
                  f"持仓: {data.get('positions', 0)} | "
                  f"当日交易: {data.get('trades', 0)}")
        elif i == 3:
            print("\n  ... (跳过中间天数)")
            
    elif event_type == 'new_trade_engine':
        event_count['new_trade_engine'] += 1
        trades.append(data)
        print(f"  >>> 交易: {data.get('action', 'unknown').upper()} {data.get('code')} "
              f"{data.get('shares')}股 @ {data.get('price', 0):.2f}")
    else:
        event_count['other'] += 1
        if event_type != 'backtest_start':
            print(f"  [其他事件] {event_type}: {data}")

duration = time.time() - start_time

print("\n" + "=" * 80)
print("汇总")
print("=" * 80)
print(f"事件统计: {event_count}")
print(f"总交易数: {len(trades)}")
print(f"回测耗时: {duration:.3f}s")

if trades:
    print("\n交易列表:")
    for trade in trades[:10]:
        print(f"  {trade.get('date')} {trade.get('action').upper():4} {trade.get('code'):>6} "
              f"{trade.get('shares'):>6}股 @ {trade.get('price', 0):>8.2f}")
