"""
检查收益计算差异
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("检查收益计算差异")
print("=" * 70)

# AquaTrade 交易记录（最新）
aqua_trades = [
    ('2025-01-21', 'buy', 11.45, 7800),
    ('2025-01-24', 'sell', 11.32, 7800),
    ('2025-02-10', 'buy', 11.38, 7800),
    ('2025-02-27', 'sell', 11.53, 7800),
    ('2025-03-10', 'buy', 11.66, 7700),
    ('2025-03-20', 'sell', 11.51, 7700),
    ('2025-04-18', 'buy', 11.04, 8000),
    ('2025-04-28', 'sell', 11.00, 8000),
    ('2025-05-12', 'buy', 11.16, 7900),
    ('2025-06-17', 'sell', 11.79, 7900),
    ('2025-06-23', 'buy', 11.81, 8000),
    ('2025-07-18', 'sell', 12.62, 8000),
    ('2025-08-08', 'buy', 12.48, 8000),
    ('2025-08-15', 'sell', 12.23, 8000),
    ('2025-08-27', 'buy', 12.32, 8000),
    ('2025-09-02', 'sell', 11.85, 8000),
    ('2025-10-16', 'buy', 11.38, 8300),
    ('2025-10-31', 'sell', 11.38, 8300),
    ('2025-11-07', 'buy', 11.52, 8200),
    ('2025-11-28', 'sell', 11.67, 8200),
    ('2025-12-19', 'buy', 11.63, 8200),
    ('2025-12-29', 'sell', 11.54, 8200),
]

# 计算详细收益
initial_capital = 100000
cash = initial_capital
position = 0
entry_price = 0
total_trades = 0
win_trades = 0
total_profit = 0

print(f"\n【交易明细】")
print(f"初始资金: {initial_capital:.2f}")

for date, action, price, qty in aqua_trades:
    if action == 'buy':
        cost = price * qty * 1.0003
        cash -= cost
        position += qty
        entry_price = price
        print(f"{date}: 买入 {qty}股 @ {price:.2f}, 成本={cost:.2f}, 现金={cash:.2f}")
    else:
        revenue = price * qty * (1 - 0.001 - 0.0003)
        profit = (price - entry_price) * qty - price * qty * 0.001 - (price + entry_price) * qty * 0.0003
        cash += revenue
        position -= qty
        total_trades += 1
        if profit > 0:
            win_trades += 1
        print(f"{date}: 卖出 {qty}股 @ {price:.2f}, 收入={revenue:.2f}, 盈亏={profit:.2f}, 现金={cash:.2f}")

final_value = cash + position * aqua_trades[-1][2]  # 使用最后价格
total_return = (final_value - initial_capital) / initial_capital * 100

print(f"\n【最终结果】")
print(f"  最终现金: {cash:.2f}")
print(f"  持仓数量: {position}")
print(f"  最终市值: {final_value:.2f}")
print(f"  总收益: {total_return:.2f}%")
print(f"  胜率: {win_trades}/{total_trades} = {win_trades/total_trades*100:.1f}%")
