"""
测试2025-01-02的买入修复
验证防止未来函数修改后，数据预加载是否正确包含前一天数据
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
print("测试2025-01-02的买入（验证数据预加载修复）")
print("=" * 60)

# 检查因子矩阵中的日期范围
start_date = '2025-01-02'
end_date = '2025-01-05'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

print(f"\n回测范围: {start_date} ~ {end_date}")
print(f"预期加载的数据应该包含: 2025-01-01（前一天）~ {end_date}")

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n实际加载的因子矩阵日期范围:")
    print(f"  开始: {fm.dates[0]}")
    print(f"  结束: {fm.dates[-1]}")
    print(f"  总天数: {len(fm.dates)}")
    print(f"  所有日期: {fm.dates}")
    
    # 检查是否包含前一天
    prev_date = '20250101'  # 2025-01-01
    if prev_date in fm.dates:
        print(f"\n✓ 成功包含前一天数据: {prev_date}")
    else:
        print(f"\n✗ 缺少前一天数据: {prev_date}")
        print(f"  这会导致2025-01-02无法生成信号！")

# 运行回测
print("\n" + "=" * 60)
print("运行回测")
print("=" * 60)

events_by_date = {}
for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    event_type = event.get('type')
    
    if event_type == 'new_trade_engine':
        t = event['data']
        date = t['date']
        if date not in events_by_date:
            events_by_date[date] = []
        events_by_date[date].append(t)

# 打印结果
print(f"\n每日交易统计:")
for date in sorted(events_by_date.keys()):
    events = events_by_date[date]
    buy_count = sum(1 for e in events if e['action'] == 'buy')
    sell_count = sum(1 for e in events if e['action'] == 'sell')
    print(f"  {date}: 买入 {buy_count}, 卖出 {sell_count}")

# 特别关注2025-01-02
jan2_key = '20250102'
if jan2_key in events_by_date:
    print(f"\n✓ 2025-01-02有 {len(events_by_date[jan2_key])} 笔交易")
    for t in events_by_date[jan2_key][:5]:  # 只显示前5笔
        print(f"  {t['code']} {t['action']} {t['shares']}股 @ {t['price']:.2f}")
else:
    print(f"\n✗ 2025-01-02没有交易")
    print(f"\n可能原因:")
    print(f"1. 2025-01-01（前一天）没有满足条件的股票")
    print(f"2. 策略的其他过滤条件没有满足")

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
total_buys = sum(sum(1 for e in events if e['action'] == 'buy') for events in events_by_date.values())
total_sells = sum(sum(1 for e in events if e['action'] == 'sell') for events in events_by_date.values())
print(f"总买入: {total_buys}")
print(f"总卖出: {total_sells}")
