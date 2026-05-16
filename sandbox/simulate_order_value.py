"""
模拟聚宽的order_value函数

聚宽代码：
order_value(stock, cash_per_stock)

这个函数会根据给定的金额买入股票，但可能因为各种原因失败：
1. 涨跌停限制
2. 资金不足
3. 股票停牌
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import polars as pl
from pathlib import Path

def simulate_order_value():
    print("模拟聚宽的order_value...")
    
    # 聚宽买入数据
    jq_trades = [
        ('000021', 10.68, 1800),  # 19224
        ('000039', 7.03, 2800),   # 19684
        ('000040', 3.66, 5400),   # 19764
        ('000049', 43.58, 400),   # 17432
    ]
    
    # 计算总成本
    total_cost = sum(price * shares for _, price, shares in jq_trades)
    print(f"\n聚宽买入总成本: {total_cost}")
    print(f"剩余资金: {100000 - total_cost}")
    
    # 检查000060
    print(f"\n如果买入000060:")
    cash_per_stock = 100000 / 5
    price_000060 = 4.10
    shares_000060 = int(cash_per_stock / price_000060 / 100) * 100
    cost_000060 = shares_000060 * price_000060
    print(f"  分配资金: {cash_per_stock}")
    print(f"  可买股数: {shares_000060}")
    print(f"  成本: {cost_000060}")
    
    # 检查聚宽的买入顺序
    print(f"\n聚宽买入顺序分析:")
    print(f"  初始资金: 100000")
    print(f"  max_hold = 5, hold_count = 0")
    print(f"  cash_per_stock = 100000 / 5 = 20000")
    
    remaining_cash = 100000
    for code, price, shares in jq_trades:
        cost = price * shares
        commission = max(cost * 0.0003, 5)
        total = cost + commission
        remaining_cash -= total
        print(f"  买入 {code}: 价格={price}, 股数={shares}, 成本={cost:.2f}, 佣金={commission:.2f}, 总计={total:.2f}")
        print(f"    剩余资金: {remaining_cash:.2f}")
    
    # 检查第5只股票
    print(f"\n  第5只股票 (000060):")
    print(f"    剩余资金: {remaining_cash:.2f}")
    print(f"    hold_count = 4, max_hold - hold_count = 1")
    print(f"    cash_per_stock = {remaining_cash:.2f} / 1 = {remaining_cash:.2f}")
    
    # 检查我们的买入
    print(f"\n我们的买入:")
    our_trades = [
        ('000021', 10.67, 1800),
        ('000039', 7.02, 2800),
        ('000040', 3.66, 5400),
        ('000049', 43.53, 400),
        ('000060', 4.10, 4800),
    ]
    
    total_cost_our = 0
    for code, price, shares in our_trades:
        cost = price * shares
        commission = max(cost * 0.0003, 5)
        total = cost + commission
        total_cost_our += total
        print(f"  买入 {code}: 价格={price}, 股数={shares}, 总计={total:.2f}")
    
    print(f"\n  总成本: {total_cost_our:.2f}")

if __name__ == "__main__":
    simulate_order_value()
