"""
检查额外交易的盈亏
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("检查额外交易的盈亏")
print("=" * 70)

# 额外交易
extra_trades = [
    ('2025-03-10', 'buy', 11.66, 7700),
    ('2025-03-20', 'sell', 11.51, 7700),
    ('2025-06-17', 'sell', 11.79, 7900),  # 这是替代聚宽的 2025-07-18 卖出
    ('2025-06-23', 'buy', 11.81, 8000),
]

# 计算盈亏
print(f"\n【额外交易盈亏】")

# 2025-03-10 买入 -> 2025-03-20 卖出
buy_cost = 11.66 * 7700 * (1 + 0.0003)
sell_revenue = 11.51 * 7700 * (1 - 0.001 - 0.0003)
profit1 = sell_revenue - buy_cost
print(f"  2025-03-10 -> 2025-03-20: 买入7700股@11.66, 卖出@11.51")
print(f"    成本: {buy_cost:.2f}, 收入: {sell_revenue:.2f}, 盈亏: {profit1:.2f}")

# 2025-06-17 卖出（替代聚宽的 2025-07-18 卖出）
# AquaTrade: 2025-05-12 买入7900股@11.16, 2025-06-17 卖出@11.79
# 聚宽: 2025-05-12 买入7900股@11.17, 2025-07-18 卖出@12.60

# AquaTrade 的 2025-06-17 卖出
buy_cost_aqua = 11.16 * 7900 * (1 + 0.0003)
sell_revenue_aqua = 11.79 * 7900 * (1 - 0.001 - 0.0003)
profit_aqua = sell_revenue_aqua - buy_cost_aqua
print(f"\n  AquaTrade: 2025-05-12 -> 2025-06-17")
print(f"    买入7900股@11.16, 卖出@11.79")
print(f"    成本: {buy_cost_aqua:.2f}, 收入: {sell_revenue_aqua:.2f}, 盈亏: {profit_aqua:.2f}")

# 聚宽的 2025-07-18 卖出
buy_cost_jq = 11.17 * 7900 * (1 + 0.0003)
sell_revenue_jq = 12.60 * 7900 * (1 - 0.001 - 0.0003)
profit_jq = sell_revenue_jq - buy_cost_jq
print(f"\n  聚宽: 2025-05-12 -> 2025-07-18")
print(f"    买入7900股@11.17, 卖出@12.60")
print(f"    成本: {buy_cost_jq:.2f}, 收入: {sell_revenue_jq:.2f}, 盈亏: {profit_jq:.2f}")

# AquaTrade 的额外交易：2025-06-23 买入 -> 2025-07-18 卖出
buy_cost_extra = 11.81 * 8000 * (1 + 0.0003)
sell_revenue_extra = 12.62 * 8000 * (1 - 0.001 - 0.0003)
profit_extra = sell_revenue_extra - buy_cost_extra
print(f"\n  AquaTrade额外: 2025-06-23 -> 2025-07-18")
print(f"    买入8000股@11.81, 卖出@12.62")
print(f"    成本: {buy_cost_extra:.2f}, 收入: {sell_revenue_extra:.2f}, 盈亏: {profit_extra:.2f}")

print(f"\n【总差异】")
print(f"  额外交易1 (03-10->03-20): {profit1:.2f}")
print(f"  AquaTrade 06-17卖出 vs 聚宽 07-18卖出: {profit_aqua:.2f} vs {profit_jq:.2f}, 差异: {profit_aqua - profit_jq:.2f}")
print(f"  AquaTrade额外 06-23->07-18: {profit_extra:.2f}")
print(f"  总差异估算: {profit1 + (profit_aqua - profit_jq) + profit_extra:.2f}")

# 加上分红
dividend = 2844.01
print(f"\n  分红: {dividend:.2f}")
print(f"  最终差异估算: {profit1 + (profit_aqua - profit_jq) + profit_extra + dividend:.2f}")
