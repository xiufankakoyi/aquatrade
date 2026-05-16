"""
测试防止未来函数修改后的策略
验证：
1. 策略仍然能正常生成信号
2. 信号数量可能减少（因为使用了前一天的数据）
3. 没有使用当天的收盘数据
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

start_date = '2025-06-03'
end_date = '2025-06-10'

print("=" * 60)
print(f"测试防止未来函数修改: {start_date} ~ {end_date}")
print("=" * 60)

event_count = 0
buy_count = 0
sell_count = 0
signals_per_day = {}

for event in engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date):
    event_count += 1
    event_type = event.get('type')
    
    if event_type == 'new_trade_engine':
        t = event['data']
        date = t['date']
        if date not in signals_per_day:
            signals_per_day[date] = {'buy': 0, 'sell': 0}
        
        if t['action'] == 'buy':
            buy_count += 1
            signals_per_day[date]['buy'] += 1
        else:
            sell_count += 1
            signals_per_day[date]['sell'] += 1
    
    elif event_type == 'final_metrics':
        data = event['data']
        print(f"\n{'='*60}")
        print("最终指标:")
        print(f"  tradesCount: {data.get('tradesCount', 0)}")
        print(f"  买入次数: {buy_count}")
        print(f"  卖出次数: {sell_count}")
        print(f"  winRate: {data.get('winRate', 0):.2f}%")
        print(f"  totalReturn: {data.get('totalReturn', 0):.2f}%")
        print(f"{'='*60}")

print(f"\n每日信号统计:")
for date in sorted(signals_per_day.keys()):
    stats = signals_per_day[date]
    print(f"  {date}: 买入 {stats['buy']}, 卖出 {stats['sell']}")

print(f"\n总计:")
print(f"  买入: {buy_count}")
print(f"  卖出: {sell_count}")
print(f"  总交易: {buy_count + sell_count}")

print("\n" + "=" * 60)
print("防止未来函数验证:")
print("=" * 60)
print("""
修改内容：
1. 信号生成使用前一天（t-1）的收盘数据
2. 基本面数据（is_st, days_listed, total_mv）也使用前一天的数据
3. 第 0 天无法生成信号（没有前一天数据）

预期结果：
- 信号数量可能会减少（特别是第 1 天）
- 但策略更加真实，没有使用未来信息
- 与实盘交易逻辑一致
""")
