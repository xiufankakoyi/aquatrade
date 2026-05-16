"""
检查策略是否存在未来函数问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_look_ahead_bias():
    print("=" * 80)
    print("检查未来函数问题")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    print("""
【问题分析】

策略逻辑：
1. 用 stock_pool_today 中的 close, ma5, ma10, ma20 做决策
2. 用当天的 open 价格买入

这是典型的未来函数问题！

当天开盘时，你不知道：
- 当天的 close（收盘价）
- 当天的 volume（成交量）
- 当天的 pct_chg（涨跌幅）

策略用这些"未来数据"判断是否"主升浪"，然后用开盘价买入。
这意味着策略"看到了未来"！

【正确的做法】
应该用"昨天"的数据做决策，然后用"今天"的开盘价买入。
""")
    
    print("\n" + "=" * 80)
    print("验证：检查策略使用的数据")
    print("=" * 80)
    
    df = data_query.get_stock_pool('2024-01-02')
    if df is not None:
        sample = df[df['stock_code'] == '603926']  # 策略第一天买入的股票
        if not sample.empty:
            row = sample.iloc[0]
            print(f"\n603926 @ 2024-01-02 (策略买入日):")
            print(f"  open: {row.get('open')}  <- 买入价格")
            print(f"  close: {row.get('close')}  <- 策略用这个判断主升浪!")
            print(f"  ma5: {row.get('ma5')}")
            print(f"  ma10: {row.get('ma10')}")
            print(f"  ma20: {row.get('ma20')}")
            
            print(f"\n  问题：策略用 close > ma5 > ma10 > ma20 判断主升浪")
            print(f"  但开盘时 close 还不知道！")
    
    print("\n" + "=" * 80)
    print("检查买入价格 vs 当日最高价")
    print("=" * 80)
    
    df = data_query.get_stock_pool('2024-01-02')
    if df is not None:
        bought_stocks = ['603926', '605167', '603111']
        for code in bought_stocks:
            stock = df[df['stock_code'] == code]
            if not stock.empty:
                row = stock.iloc[0]
                open_p = row.get('open', 0)
                close = row.get('close', 0)
                high = row.get('high', 0)
                pct = (close / open_p - 1) * 100 if open_p > 0 else 0
                
                print(f"\n{code}:")
                print(f"  开盘 {open_p:.2f} -> 收盘 {close:.2f} (当日涨幅 {pct:.1f}%)")
                print(f"  最高 {high:.2f}")


if __name__ == "__main__":
    check_look_ahead_bias()
