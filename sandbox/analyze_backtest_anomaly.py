"""
深入分析 simple_volume_v3 策略回测异常
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


def analyze_backtest():
    print("=" * 80)
    print("深入分析回测异常")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    strategy = SimpleVolumeStrategyV3()
    
    start_date = "2024-09-01"
    end_date = "2024-11-21"
    
    all_trades = []
    daily_equity = []
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'daily_equity_engine':
            daily_equity.append({
                'date': data.get('date'),
                'equity': safe_float(data.get('equity')),
            })
        elif update_type in ('new_trade', 'new_trade_engine'):
            all_trades.append(data)
    
    closed_trades = [t for t in all_trades if t.get('action') == 'sell']
    
    print("\n" + "=" * 80)
    print("【问题1: 北交所股票分析】(920开头)")
    print("=" * 80)
    
    bse_trades = [t for t in closed_trades if str(t.get('symbol', '')).startswith('920')]
    print(f"\n北交所平仓交易数: {len(bse_trades)}")
    
    if bse_trades:
        bse_profit = sum(safe_float(t.get('profit_loss')) for t in bse_trades)
        print(f"北交所总盈亏: {bse_profit:.2f}")
        print("\n北交所交易详情:")
        for t in bse_trades:
            print(f"  {t.get('date')} | {t.get('symbol')} | "
                  f"价格: {safe_float(t.get('price')):.2f} | "
                  f"盈亏: {safe_float(t.get('profit_loss')):.2f} | "
                  f"ROI: {safe_float(t.get('roi')):.2f}%")
    
    print("\n" + "=" * 80)
    print("【问题2: 单笔大额盈利分析】")
    print("=" * 80)
    
    sorted_trades = sorted(closed_trades, key=lambda x: safe_float(x.get('profit_loss')), reverse=True)
    print("\n盈利最大的10笔交易:")
    for i, t in enumerate(sorted_trades[:10], 1):
        print(f"  [{i}] {t.get('date')} | {t.get('symbol')} | "
              f"买入价: {safe_float(t.get('entry_price')):.2f} | "
              f"卖出价: {safe_float(t.get('price')):.2f} | "
              f"盈亏: {safe_float(t.get('profit_loss')):.2f} | "
              f"ROI: {safe_float(t.get('roi')):.2f}%")
    
    print("\n" + "=" * 80)
    print("【问题3: 涨跌幅异常分析】")
    print("=" * 80)
    
    abnormal_trades = []
    for t in closed_trades:
        roi = safe_float(t.get('roi'))
        if abs(roi) > 10:
            abnormal_trades.append(t)
    
    print(f"\n单笔盈亏超过10%的交易数: {len(abnormal_trades)}")
    if abnormal_trades:
        print("\n异常交易详情:")
        for t in abnormal_trades[:20]:
            entry = safe_float(t.get('entry_price'))
            exit_p = safe_float(t.get('price'))
            roi = safe_float(t.get('roi'))
            print(f"  {t.get('date')} | {t.get('symbol')} | "
                  f"买入: {entry:.2f} -> 卖出: {exit_p:.2f} | "
                  f"涨跌: {(exit_p/entry-1)*100:.1f}% | ROI: {roi:.1f}%")
    
    print("\n" + "=" * 80)
    print("【问题4: 按日期统计盈亏】")
    print("=" * 80)
    
    df_trades = pd.DataFrame(closed_trades)
    if not df_trades.empty:
        df_trades['profit_loss'] = df_trades['profit_loss'].apply(safe_float)
        daily_pnl = df_trades.groupby('date')['profit_loss'].sum().sort_values(ascending=False)
        
        print("\n盈利最多的5天:")
        for date, pnl in daily_pnl.head(5).items():
            trades_that_day = df_trades[df_trades['date'] == date]
            print(f"  {date}: +{pnl:.2f} ({len(trades_that_day)}笔交易)")
        
        print("\n亏损最多的5天:")
        for date, pnl in daily_pnl.tail(5).items():
            trades_that_day = df_trades[df_trades['date'] == date]
            print(f"  {date}: {pnl:.2f} ({len(trades_that_day)}笔交易)")
    
    print("\n" + "=" * 80)
    print("【问题5: 9月底大涨分析】")
    print("=" * 80)
    
    sep_trades = [t for t in closed_trades if t.get('date', '').startswith('2024-09')]
    sep_profit = sum(safe_float(t.get('profit_loss')) for t in sep_trades)
    print(f"\n9月份平仓盈亏: {sep_profit:.2f}")
    print(f"9月份平仓笔数: {len(sep_trades)}")
    
    oct_trades = [t for t in closed_trades if t.get('date', '').startswith('2024-10')]
    oct_profit = sum(safe_float(t.get('profit_loss')) for t in oct_trades)
    print(f"\n10月份平仓盈亏: {oct_profit:.2f}")
    print(f"10月份平仓笔数: {len(oct_trades)}")
    
    nov_trades = [t for t in closed_trades if t.get('date', '').startswith('2024-11')]
    nov_profit = sum(safe_float(t.get('profit_loss')) for t in nov_trades)
    print(f"\n11月份平仓盈亏: {nov_profit:.2f}")
    print(f"11月份平仓笔数: {len(nov_trades)}")
    
    print("\n" + "=" * 80)
    print("【问题6: 检查数据源】")
    print("=" * 80)
    
    sample_codes = ['603890', '920418', '600239']
    for code in sample_codes:
        try:
            df = data_query.get_stock_daily_data(code, '2024-09-01', '2024-11-21')
            if df is not None and not df.empty:
                print(f"\n{code} 数据样例:")
                print(df.head(3).to_string())
        except Exception as e:
            print(f"\n{code} 获取数据失败: {e}")


if __name__ == "__main__":
    analyze_backtest()
