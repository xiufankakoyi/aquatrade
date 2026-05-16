"""
测试 simple_volume_v3 策略回测
重点分析平仓记录，验证收益异常问题
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.logger import get_logger

logger = get_logger(__name__)


def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run_backtest_test():
    print("=" * 80)
    print("Simple Volume V3 策略回测测试")
    print("时间范围: 2024-09-01 ~ 2024-11-21")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    
    strategy = SimpleVolumeStrategyV3()
    
    start_date = "2024-09-01"
    end_date = "2024-11-21"
    
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
        elif update_type == 'progress':
            pass
    
    print("\n" + "=" * 80)
    print("回测完成!")
    print("=" * 80)
    
    if final_metrics:
        print("\n【绩效指标】")
        print(f"  总收益率: {safe_float(final_metrics.get('total_return_pct')):.2f}%")
        print(f"  年化收益: {safe_float(final_metrics.get('annualized_return_pct')):.2f}%")
        print(f"  最大回撤: {safe_float(final_metrics.get('max_drawdown_pct')):.2f}%")
        print(f"  夏普比率: {safe_float(final_metrics.get('sharpe_ratio')):.2f}")
        print(f"  胜率: {safe_float(final_metrics.get('win_rate_pct')):.2f}%")
        print(f"  盈亏比: {safe_float(final_metrics.get('profit_loss_ratio')):.2f}")
        print(f"  总交易次数: {final_metrics.get('total_trades', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("【所有平仓记录】")
    print("=" * 80)
    
    closed_trades = [t for t in all_trades if t.get('action') == 'sell']
    
    if not closed_trades:
        print("没有平仓记录")
    else:
        print(f"\n共 {len(closed_trades)} 笔平仓:\n")
        
        total_profit = 0
        win_count = 0
        loss_count = 0
        
        for i, trade in enumerate(closed_trades, 1):
            profit = safe_float(trade.get('profit_loss'))
            roi = safe_float(trade.get('roi'))
            total_profit += profit
            
            if profit > 0:
                win_count += 1
                result = "✅ 盈利"
            elif profit < 0:
                loss_count += 1
                result = "❌ 亏损"
            else:
                result = "➖ 持平"
            
            print(f"[{i:3d}] {trade.get('date', 'N/A')} | {str(trade.get('symbol', 'N/A')):6s} | "
                  f"价格: {safe_float(trade.get('price')):8.2f} | 数量: {int(safe_float(trade.get('quantity', 0))):>6d} | "
                  f"盈亏: {profit:>10.2f} | ROI: {roi:>7.2f}% | {result}")
        
        print("\n" + "-" * 80)
        print(f"总盈亏: {total_profit:.2f}")
        print(f"盈利次数: {win_count}, 亏损次数: {loss_count}")
        if win_count + loss_count > 0:
            print(f"实际胜率: {win_count / (win_count + loss_count) * 100:.2f}%")
    
    print("\n" + "=" * 80)
    print("【买入记录】")
    print("=" * 80)
    
    buy_trades = [t for t in all_trades if t.get('action') == 'buy']
    
    if buy_trades:
        print(f"\n共 {len(buy_trades)} 笔买入:\n")
        for i, trade in enumerate(buy_trades[:50], 1):
            print(f"[{i:3d}] {trade.get('date', 'N/A')} | {str(trade.get('symbol', 'N/A')):6s} | "
                  f"价格: {safe_float(trade.get('price')):8.2f} | 数量: {int(safe_float(trade.get('quantity', 0))):>6d}")
        
        if len(buy_trades) > 50:
            print(f"... 还有 {len(buy_trades) - 50} 笔买入记录")
    
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
        
        print("\n【每日权益变化】(每10天)")
        for i in range(0, len(df_equity), 10):
            row = df_equity.iloc[i]
            print(f"  {row['date']}: 权益 {row['equity']:.2f} | 现金 {row['cash']:.2f} | 持仓 {row['positions']}")


if __name__ == "__main__":
    run_backtest_test()
