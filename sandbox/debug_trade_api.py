"""
调试交易执行 - 使用 API 方式
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import pandas as pd
from data_svc.unified_data_manager import UnifiedDataManager
from api.backtest import run_backtest
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy

# 初始化数据管理器
print("初始化数据查询...")
data_manager = UnifiedDataManager()

# 创建策略
strategy = MainWaveTrendStrategy(
    data_manager=data_manager,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

# 运行回测
print("\n运行回测...")
print("=" * 80)

result = run_backtest(
    strategy=strategy,
    start_date="2024-01-02",
    end_date="2024-01-10",
    initial_capital=1000000.0,
    commission_rate=0.0003,
    position_ratio=0.1,
    max_positions=10,
    mode='vectorized'
)

# 检查结果
print("\n" + "=" * 80)
print("回测结果:")
print("=" * 80)
print(f"最终权益: {result.final_equity:,.2f}")
print(f"总收益率: {result.total_return:.2f}%")
print(f"交易次数: {result.trade_count}")
print(f"最大回撤: {result.max_drawdown:.2f}%")

# 获取交易记录
if hasattr(result, 'trades') and result.trades:
    print(f"\n交易记录数量: {len(result.trades)}")
    buy_trades = [t for t in result.trades if t.action == 'buy']
    sell_trades = [t for t in result.trades if t.action == 'sell']
    print(f"买入交易: {len(buy_trades)}")
    print(f"卖出交易: {len(sell_trades)}")
    
    if result.trades:
        print("\n前10笔交易:")
        for trade in result.trades[:10]:
            print(f"  {trade.date} {trade.action.upper():4} {trade.code:>6} {trade.shares:>6}股 @ {trade.price:>8.2f}")
else:
    print("\n没有交易记录!")

# 检查权益曲线
if hasattr(result, 'equity_curve') and result.equity_curve:
    print(f"\n权益曲线数据点: {len(result.equity_curve)}")
    print(f"首日权益: {result.equity_curve[0][1]:,.2f}")
    print(f"末日权益: {result.equity_curve[-1][1]:,.2f}")
else:
    print("\n没有权益曲线数据!")
