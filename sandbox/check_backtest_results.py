"""
检查回测结果
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
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
start_date = '2025-06-02'
end_date = '2026-01-10'

print("=" * 80)
print("检查回测结果")
print("=" * 80)

# 运行回测
results_gen = engine.run_backtest(
    strategy=strategy,
    start_date=start_date,
    end_date=end_date
)

# 收集所有结果
results = None
for event in results_gen:
    event_type = event.get('type')
    if event_type == 'stream_complete':
        results = event.get('data')
        break

if results is None:
    print("没有收到回测结果")
    sys.exit(1)

print(f"\n回测结果:")
print(f"  初始资金: {config.initial_capital:,.2f}")
print(f"  最终权益: {results['finalEquity']:,.2f}")
print(f"  总收益率: {results['totalReturn']:.2f}%")
print(f"  年化收益率: {results['annualizedReturn']:.2f}%")
print(f"  最大回撤: {results['maxDrawdown']:.2f}%")
print(f"  夏普比率: {results['sharpeRatio']:.2f}")
print(f"  总交易数: {results['totalTrades']}")
print(f"  胜率: {results['winRate']:.2f}%")
print(f"  盈亏比: {results['profitFactor']:.2f}")

# 检查权益曲线
equity_curve = results['equityCurve']
print(f"\n权益曲线:")
for point in equity_curve:
    print(f"  {point['date']}: {point['equity']:,.2f}")

# 检查交易列表
trades = results['trades']
print(f"\n交易列表 (共 {len(trades)} 笔):")
for trade in trades:
    print(f"  {trade['date']} {trade['action'].upper():4s} {trade['code']:6s} {trade['shares']:6d}股 @ {trade['price']:8.2f}")
