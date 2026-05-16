"""
验证策略是否"预知"当天涨跌
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


def analyze_buy_day_performance():
    print("=" * 80)
    print("分析买入当天的股票表现")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    strategy = SimpleVolumeStrategyV3()
    
    start_date = "2024-01-01"
    end_date = "2024-03-31"
    
    all_trades = []
    
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type in ('new_trade', 'new_trade_engine'):
            all_trades.append(data)
    
    buy_trades = [t for t in all_trades if t.get('action') == 'buy']
    
    print(f"\n买入交易数: {len(buy_trades)}")
    
    daily_changes = []
    
    for trade in buy_trades:
        date = trade.get('date')
        code = trade.get('code') or trade.get('stock_code')
        buy_price = safe_float(trade.get('price'))
        
        df = data_query.get_stock_pool(date)
        if df is not None:
            stock = df[df['stock_code'] == code]
            if not stock.empty:
                row = stock.iloc[0]
                open_p = safe_float(row.get('open'))
                close_p = safe_float(row.get('close'))
                high_p = safe_float(row.get('high'))
                low_p = safe_float(row.get('low'))
                
                if open_p > 0:
                    day_change = (close_p / open_p - 1) * 100
                    intraday_range = (high_p - low_p) / open_p * 100 if open_p > 0 else 0
                    
                    daily_changes.append({
                        'date': date,
                        'code': code,
                        'open': open_p,
                        'close': close_p,
                        'day_change': day_change,
                        'intraday_range': intraday_range,
                        'buy_price': buy_price
                    })
    
    if daily_changes:
        df_changes = pd.DataFrame(daily_changes)
        
        print("\n" + "=" * 80)
        print("买入当天股票表现统计")
        print("=" * 80)
        
        up_days = len(df_changes[df_changes['day_change'] > 0])
        down_days = len(df_changes[df_changes['day_change'] < 0])
        flat_days = len(df_changes[df_changes['day_change'] == 0])
        
        print(f"\n上涨天数: {up_days} ({up_days/len(df_changes)*100:.1f}%)")
        print(f"下跌天数: {down_days} ({down_days/len(df_changes)*100:.1f}%)")
        print(f"平盘天数: {flat_days} ({flat_days/len(df_changes)*100:.1f}%)")
        
        print(f"\n平均当日涨幅: {df_changes['day_change'].mean():.2f}%")
        print(f"最大当日涨幅: {df_changes['day_change'].max():.2f}%")
        print(f"最大当日跌幅: {df_changes['day_change'].min():.2f}%")
        
        print("\n" + "=" * 80)
        print("【关键问题】")
        print("=" * 80)
        
        if up_days / len(df_changes) > 0.7:
            print(f"""
⚠️ 买入当天上涨概率: {up_days/len(df_changes)*100:.1f}%
这远高于随机概率(约50%)，说明策略存在未来函数问题！

策略用当天的 close/ma 数据判断是否买入，
然后用当天的 open 价格买入。
这意味着策略"知道"当天会涨才买入。
""")
        else:
            print(f"买入当天上涨概率: {up_days/len(df_changes)*100:.1f}%，看起来正常")
        
        print("\n前10笔买入交易:")
        print(df_changes[['date', 'code', 'open', 'close', 'day_change']].head(10).to_string())


if __name__ == "__main__":
    analyze_buy_day_performance()
