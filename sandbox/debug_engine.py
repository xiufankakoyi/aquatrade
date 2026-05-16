"""调试引擎买入逻辑"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np

# 模拟参数
cash = 1000000.0
commission_rate = 0.0003
buy_price = 14.97

# 计算过程
available_cash = cash * 0.95 / (1 + commission_rate)
print(f"可用资金 (预留佣金后): {available_cash:,.2f}")

cash_per_stock = available_cash  # 只有一只股票
print(f"每只股票可用资金: {cash_per_stock:,.2f}")

# 计算股数
shares = int(cash_per_stock / buy_price / 100) * 100
print(f"计算股数: {shares}")

# 计算成本
stock_cost = shares * buy_price
commission = stock_cost * commission_rate
total_cost = stock_cost + commission

print(f"\n成本明细:")
print(f"  股票成本: {stock_cost:,.2f}")
print(f"  佣金: {commission:,.2f}")
print(f"  总成本: {total_cost:,.2f}")

remaining_cash = cash - total_cost
print(f"\n剩余现金:")
print(f"  预期: {remaining_cash:,.2f}")
print(f"  实际 (从测试): 51,064.40")
print(f"  差额: {remaining_cash - 51064.40:,.2f}")

# 反推实际买入价格
actual_shares = 62700
actual_position_value = 938619.00
actual_buy_price = actual_position_value / actual_shares
print(f"\n反推实际买入价: {actual_buy_price:.4f}")

# 如果按实际价格计算
actual_stock_cost = actual_shares * actual_buy_price
actual_commission = actual_stock_cost * commission_rate
actual_total_cost = actual_stock_cost + actual_commission
actual_remaining = cash - actual_total_cost
print(f"按实际价格计算的剩余现金: {actual_remaining:,.2f}")
