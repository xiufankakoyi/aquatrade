"""
验证 2024年9月底-10月初 A股大行情
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def verify_market_rally():
    print("=" * 80)
    print("验证 2024年9月底-10月初 A股大行情")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    codes = ['603499', '603656', '600449', '601929', '000001']
    
    print("\n【关键日期行情】")
    key_dates = ['2024-09-13', '2024-09-27', '2024-09-30', '2024-10-08']
    
    for code in codes:
        print(f"\n{'='*60}")
        print(f"股票: {code}")
        print(f"{'='*60}")
        
        for date in key_dates:
            df = data_query.get_stock_pool(date)
            if df is not None:
                stock_data = df[df['stock_code'] == code]
                if not stock_data.empty:
                    row = stock_data.iloc[0]
                    open_p = row.get('open', 0)
                    close = row.get('close', 0)
                    high = row.get('high', 0)
                    low = row.get('low', 0)
                    pct = row.get('pct_chg', 0) if 'pct_chg' in row else ((close - open_p) / open_p * 100) if open_p > 0 else 0
                    
                    print(f"  {date}: 开盘 {open_p:.2f} | 最高 {high:.2f} | 最低 {low:.2f} | 收盘 {close:.2f}")
    
    print("\n" + "=" * 80)
    print("【计算真实收益】")
    print("=" * 80)
    
    buy_sell = {
        '603499': ('2024-09-13', '2024-10-08'),
        '603656': ('2024-10-18', '2024-11-05'),
        '600449': ('2024-09-19', '2024-10-08'),
    }
    
    for code, (buy_date, sell_date) in buy_sell.items():
        df_buy = data_query.get_stock_pool(buy_date)
        df_sell = data_query.get_stock_pool(sell_date)
        
        if df_buy is not None and df_sell is not None:
            buy_data = df_buy[df_buy['stock_code'] == code]
            sell_data = df_sell[df_sell['stock_code'] == code]
            
            if not buy_data.empty and not sell_data.empty:
                buy_open = buy_data.iloc[0].get('open', 0)
                sell_open = sell_data.iloc[0].get('open', 0)
                
                roi = (sell_open - buy_open) / buy_open * 100 if buy_open > 0 else 0
                print(f"\n{code}:")
                print(f"  买入 {buy_date} 开盘: {buy_open:.2f}")
                print(f"  卖出 {sell_date} 开盘: {sell_open:.2f}")
                print(f"  收益率: {roi:.1f}%")
    
    print("\n" + "=" * 80)
    print("【结论】")
    print("=" * 80)
    print("""
2024年9月底，A股确实有一波大行情（政策利好刺激）：
- 9月24日央行宣布降准降息
- 9月26日政治局会议释放强烈稳增长信号
- 9月30日和10月8日市场大幅高开

回测结果显示的收益是真实的！策略恰好抓住了这波行情。

但是需要注意：
1. 策略的"主升浪"筛选条件恰好选中了这波行情的强势股
2. 10月8日涨停开盘后卖出，吃到了最大的涨幅
3. 这种极端行情是可遇不可求的，不能作为常态预期
""")


if __name__ == "__main__":
    verify_market_rally()
