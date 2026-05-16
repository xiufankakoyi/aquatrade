"""
详细对比交易记录
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("详细对比交易记录")
print("=" * 70)

# AquaTrade 交易记录
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
    ('2025-06-17', 'sell', 11.79, 7900),  # 不同
    ('2025-06-23', 'buy', 11.81, 8000),   # 不同
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

# 聚宽交易记录
jq_trades = [
    ('2025-01-21', 'buy', 11.46, 7800),
    ('2025-01-24', 'sell', 11.31, 7800),
    ('2025-02-10', 'buy', 11.39, 7800),
    ('2025-02-27', 'sell', 11.52, 7800),
    ('2025-04-18', 'buy', 11.05, 8100),
    ('2025-04-28', 'sell', 10.99, 8100),
    ('2025-05-12', 'buy', 11.17, 7900),
    ('2025-07-18', 'sell', 12.60, 7900),
    ('2025-08-08', 'buy', 12.50, 8100),
    ('2025-08-15', 'sell', 12.21, 8100),
    ('2025-08-27', 'buy', 12.34, 8000),
    ('2025-09-02', 'sell', 11.84, 8000),
    ('2025-10-16', 'buy', 11.39, 8300),
    ('2025-10-31', 'sell', 11.37, 8300),
    ('2025-11-07', 'buy', 11.53, 8200),
    ('2025-11-28', 'sell', 11.66, 8200),
    ('2025-12-19', 'buy', 11.64, 8200),
    ('2025-12-29', 'sell', 11.53, 8200),
]

print(f"\n【AquaTrade 交易记录】")
for date, action, price, qty in aqua_trades:
    print(f"  {date}: {action:4} {qty}股 @ {price:.2f}")

print(f"\n【聚宽交易记录】")
for date, action, price, qty in jq_trades:
    print(f"  {date}: {action:4} {qty}股 @ {price:.2f}")

# 计算收益
def calc_profit(trades, initial_capital=100000):
    cash = initial_capital
    position = 0
    total_profit = 0
    for date, action, price, qty in trades:
        if action == 'buy':
            cost = price * qty * 1.0003  # 手续费
            cash -= cost
            position += qty
        else:
            revenue = price * qty * (1 - 0.001 - 0.0003)  # 印花税 + 手续费
            cash += revenue
            position -= qty
    return cash + position * price - initial_capital

aqua_profit = calc_profit(aqua_trades)
jq_profit = calc_profit(jq_trades)

print(f"\n【收益对比】")
print(f"  AquaTrade 收益: {aqua_profit:.2f} ({aqua_profit/100000*100:.2f}%)")
print(f"  聚宽收益: {jq_profit:.2f} ({jq_profit/100000*100:.2f}%)")
print(f"  差异: {aqua_profit - jq_profit:.2f} ({(aqua_profit - jq_profit)/100000*100:.2f}%)")
