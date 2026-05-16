"""
调试交易执行
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import numpy as np
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

start_date = '2025-06-03'
end_date = '2025-06-10'

# 预加载数据
query.preload_backtest_data(start_date, end_date)
preloaded = getattr(query, '_preloaded_data', None)

time_series = pd.date_range(start=start_date, end=end_date, freq='B')

# 模拟回测循环
portfolio = {}
cash = 1000000.0
position_info = {}

for idx, current_time in enumerate(time_series, 1):
    print(f"\n{'='*60}")
    print(f"Day {idx}: {current_time.strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    
    # 加载当日数据
    stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
    print(f"data_dict 股票数: {len(data_dict) if data_dict else 0}")
    
    # 生成信号
    signals = engine._generate_signals(
        strategy, current_time, stock_pool, preloaded, idx, time_series
    )
    print(f"信号数: {len(signals)}")
    
    if signals:
        # 检查信号中的股票是否在 data_dict 中
        matched = sum(1 for code in signals.keys() if code in data_dict)
        print(f"信号匹配 data_dict: {matched}/{len(signals)}")
        
        # 显示前5个信号
        for i, (code, sig) in enumerate(list(signals.items())[:5]):
            in_dict = code in data_dict
            data = data_dict.get(code, {})
            print(f"  {code}: {sig.get('action')} - in_dict={in_dict}, open={data.get('open')}")
    
    # 执行交易
    if signals and data_dict:
        portfolio, cash, trades = engine._execute_trades(
            current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
        )
        print(f"交易数: {len(trades)}")
        for trade in trades[:3]:
            print(f"  {trade.code}: {trade.action} {trade.shares} @ {trade.price}")
    
    print(f"持仓数: {len(portfolio)}, 现金: {cash:,.2f}")
    
    if idx >= 3:
        break
