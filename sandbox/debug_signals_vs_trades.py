"""
调试信号与交易 - 检查为什么有信号但没有交易
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

start_date = '2025-06-03'
end_date = '2025-06-10'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# 获取时间序列
time_series = engine._get_time_series(start_ts, end_ts)
print(f"时间序列 ({len(time_series)} 天): {[t.strftime('%Y-%m-%d') for t in time_series]}")

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)
print(f"\n预加载数据完成")

# 检查因子矩阵
if engine._factor_matrix is not None:
    fm = engine._factor_matrix
    print(f"\n因子矩阵信息:")
    print(f"  日期数: {len(fm.dates)}")
    print(f"  日期范围: {fm.dates[0]} ~ {fm.dates[-1]}")
    print(f"  股票数: {len(fm.codes_str)}")

# 模拟回测循环
print(f"\n{'='*80}")
print("开始模拟回测循环 - 详细检查信号与交易")
print(f"{'='*80}")

portfolio = {}
cash = config.initial_capital
position_info = {}

for idx, current_time in enumerate(time_series, 1):
    date_str = current_time.strftime('%Y-%m-%d')
    print(f"\n{'='*80}")
    print(f"Day {idx}: {date_str}")
    print(f"{'='*80}")
    print(f"  当前现金: {cash:.2f}")
    print(f"  当前持仓: {len(portfolio)} 只股票")
    
    # 加载当日数据
    stock_pool, use_pl, data_dict = engine._load_day_data(current_time)
    print(f"  data_dict 股票数: {len(data_dict) if data_dict else 0}")
    
    # 生成信号
    signals = engine._generate_signals(
        strategy, current_time, stock_pool, preloaded_data, idx, time_series
    )
    print(f"  信号数: {len(signals)}")
    
    if signals:
        buy_signals = {k: v for k, v in signals.items() if v.get('action') == 'buy'}
        sell_signals = {k: v for k, v in signals.items() if v.get('action') == 'sell'}
        print(f"    buy: {len(buy_signals)}, sell: {len(sell_signals)}")
        
        # 检查前5个买入信号的数据
        if buy_signals:
            print(f"\n  前5个买入信号详情:")
            for i, (code, sig) in enumerate(list(buy_signals.items())[:5]):
                data = data_dict.get(code, {})
                print(f"    {code}: open={data.get('open')}, is_suspended={data.get('is_suspended')}, is_limit_up={data.get('is_limit_up')}")
    
    # 执行交易
    new_portfolio, new_cash, trades = engine._execute_trades(
        current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
    )
    
    print(f"  交易数: {len(trades)}")
    for trade in trades:
        print(f"    {trade.action}: {trade.code} {trade.shares}股 @ {trade.price:.2f}")
    
    # 更新状态
    portfolio = new_portfolio
    cash = new_cash
    
    print(f"  更新后现金: {cash:.2f}")
    print(f"  更新后持仓: {len(portfolio)} 只股票")
    if portfolio:
        print(f"    持仓: {list(portfolio.keys())[:5]}...")

print(f"\n{'='*80}")
print("模拟回测循环结束")
print(f"{'='*80}")
print(f"最终现金: {cash:.2f}")
print(f"最终持仓: {portfolio}")
