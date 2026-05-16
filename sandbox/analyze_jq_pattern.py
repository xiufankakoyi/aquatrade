"""
分析聚宽交易记录的模式
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("分析聚宽交易记录的模式")
print("=" * 70)

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

# AquaTrade交易记录
aqua_trades = [
    ('2025-01-21', 'buy', 11.45, 7800),
    ('2025-01-24', 'sell', 11.32, 7800),
    ('2025-02-10', 'buy', 11.38, 7800),
    ('2025-02-27', 'sell', 11.53, 7800),
    ('2025-03-10', 'buy', 11.66, 7700),  # 额外
    ('2025-03-20', 'sell', 11.51, 7700),  # 额外
    ('2025-04-18', 'buy', 11.04, 8000),
    ('2025-04-28', 'sell', 11.00, 8000),
    ('2025-05-12', 'buy', 11.16, 7900),
    ('2025-06-17', 'sell', 11.79, 7900),  # 不同
    ('2025-06-23', 'buy', 11.81, 8000),   # 额外
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

print(f"\n【交易日期对比】")
print(f"  {'日期':<12} {'聚宽':<10} {'AquaTrade':<10}")
print(f"  {'-'*32}")

jq_dates = set(t[0] for t in jq_trades)
aqua_dates = set(t[0] for t in aqua_trades)

all_dates = sorted(jq_dates | aqua_dates)
for date in all_dates:
    jq_action = next((t[1] for t in jq_trades if t[0] == date), '')
    aqua_action = next((t[1] for t in aqua_trades if t[0] == date), '')
    
    marker = ''
    if date in jq_dates and date not in aqua_dates:
        marker = ' <-- 仅聚宽'
    elif date in aqua_dates and date not in jq_dates:
        marker = ' <-- 仅AquaTrade'
    elif jq_action != aqua_action:
        marker = ' <-- 动作不同'
    
    print(f"  {date:<12} {jq_action:<10} {aqua_action:<10}{marker}")

print(f"\n【差异分析】")
print(f"  聚宽交易次数: {len(jq_trades)}")
print(f"  AquaTrade交易次数: {len(aqua_trades)}")
print(f"  额外交易: {len(aqua_trades) - len(jq_trades)}")

print(f"\n【可能的原因】")
print(f"  1. 聚宽使用了不同的数据源")
print(f"  2. 聚宽在 2025-03-07 没有检测到金叉")
print(f"  3. 聚宽在 2025-06-20 没有检测到金叉")
print(f"  4. 聚宽可能有额外的信号过滤逻辑")
