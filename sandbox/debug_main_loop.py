"""
调试主循环中的信号生成
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
start_date = '2024-01-02'
end_date = '2024-01-10'

print("=" * 80)
print("调试主循环中的信号生成")
print("=" * 80)

# 手动调用回测步骤
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
print(f"\n时间序列: {[ts.strftime('%Y-%m-%d') for ts in time_series]}")

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

print(f"\n预加载数据键: {list(preloaded_data.keys())}")

# 模拟主循环
portfolio = {}
cash = config.initial_capital
position_info = {}

for idx, current_time in enumerate(time_series, 1):
    date_str = current_time.strftime('%Y-%m-%d')
    print(f"\n{'='*60}")
    print(f"第 {idx} 天: {date_str}")
    print(f"{'='*60}")
    
    # 加载当日数据
    stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
    
    print(f"股票池类型: {type(stock_pool)}")
    if isinstance(stock_pool, np.ndarray):
        print(f"股票池大小: {len(stock_pool)}")
    
    # 生成信号
    signals = engine._generate_signals(
        strategy, current_time, stock_pool, preloaded_data, idx, time_series
    )
    
    print(f"信号数量: {len(signals)}")
    
    buy_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'buy'}
    sell_signals = {k: v for k, v in signals.items() if isinstance(v, dict) and v.get('action') == 'sell'}
    
    print(f"买入信号: {len(buy_signals)}")
    print(f"卖出信号: {len(sell_signals)}")
    
    if buy_signals:
        print(f"买入股票示例: {list(buy_signals.keys())[:5]}")
    
    # 只处理前两天
    if idx >= 2:
        break
