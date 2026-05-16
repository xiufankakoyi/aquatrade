"""
测试 simple_volume_v3 策略 2024.1.1 - 2026.1.31
修复字段名匹配问题
"""
import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run_backtest():
    print("=" * 80)
    print("Simple Volume V3 策略回测测试")
    print("时间范围: 2024-01-01 ~ 2026-01-31")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    strategy = SimpleVolumeStrategyV3()
    
    start_date = "2024-01-01"
    end_date = "2026-01-31"
    
    all_trades = []
    daily_equity = []
    final_metrics = None
    
    print(f"\n开始回测...")
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'daily_equity_engine':
            daily_equity.append({
                'date': data.get('date'),
                'equity': safe_float(data.get('equity')),
                'cash': safe_float(data.get('cash')),
                'positions': data.get('positions', 0),
            })
        elif update_type in ('new_trade', 'new_trade_engine'):
            all_trades.append(data)
        elif update_type == 'final_metrics':
            final_metrics = data
            print(f"\n收到 final_metrics: {list(data.keys())}")
    
    print("\n" + "=" * 80)
    print("回测完成!")
    print("=" * 80)
    
    if final_metrics:
        print("\n【引擎计算的绩效指标】")
        print(f"  totalReturn: {final_metrics.get('totalReturn')}")
        print(f"  annualizedReturn: {final_metrics.get('annualizedReturn')}")
        print(f"  maxDrawdown: {final_metrics.get('maxDrawdown')}")
        print(f"  sharpeRatio: {final_metrics.get('sharpeRatio')}")
        print(f"  winRate: {final_metrics.get('winRate')}")
        print(f"  tradesCount: {final_metrics.get('tradesCount')}")
    
    if daily_equity:
        df_equity = pd.DataFrame(daily_equity)
        print("\n" + "=" * 80)
        print("【权益曲线摘要】")
        print("=" * 80)
        print(f"\n起始权益: {df_equity['equity'].iloc[0]:.2f}")
        print(f"结束权益: {df_equity['equity'].iloc[-1]:.2f}")
        print(f"最高权益: {df_equity['equity'].max():.2f}")
        print(f"最低权益: {df_equity['equity'].min():.2f}")
        
        actual_return = (df_equity['equity'].iloc[-1] / df_equity['equity'].iloc[0] - 1) * 100
        print(f"\n实际收益率: {actual_return:.2f}%")
    
    closed_trades = [t for t in all_trades if t.get('action') == 'sell']
    print(f"\n【交易统计】")
    print(f"  总买入: {len([t for t in all_trades if t.get('action') == 'buy'])}")
    print(f"  总卖出: {len(closed_trades)}")
    
    if closed_trades:
        total_profit = sum(safe_float(t.get('profit_loss')) for t in closed_trades)
        print(f"  总盈亏: {total_profit:.2f}")
        
        wins = [t for t in closed_trades if safe_float(t.get('profit_loss')) > 0]
        losses = [t for t in closed_trades if safe_float(t.get('profit_loss')) < 0]
        print(f"  盈利次数: {len(wins)}, 亏损次数: {len(losses)}")


if __name__ == "__main__":
    run_backtest()
