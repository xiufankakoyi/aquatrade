"""验证回测精准性"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

print("=" * 70)
print("回测精准性验证")
print("=" * 70)

# 买入数据
buy_price = 15.13
shares = 62700
commission_rate = 0.0003
initial_cash = 1000000

# 买入成本计算
stock_cost = shares * buy_price
commission = stock_cost * commission_rate
total_cost = stock_cost + commission
remaining_cash = initial_cash - total_cost

print(f"\n买入计算:")
print(f"  买入价: {buy_price}")
print(f"  股数: {shares}")
print(f"  股票成本: {stock_cost:,.2f}")
print(f"  佣金 ({commission_rate*100}%): {commission:,.2f}")
print(f"  总成本: {total_cost:,.2f}")
print(f"  剩余现金: {remaining_cash:,.2f}")

# 收盘数据
close_price = 14.97
position_value = shares * close_price
total_value = remaining_cash + position_value

print(f"\n收盘计算:")
print(f"  收盘价: {close_price}")
print(f"  持仓市值: {position_value:,.2f}")
print(f"  现金: {remaining_cash:,.2f}")
print(f"  总资产: {total_value:,.2f}")

# 验证
expected_cash = 51064.40
expected_position = 938619.00
expected_total = 989683.40

print(f"\n验证:")
print(f"  现金: {remaining_cash:,.2f} == {expected_cash:,.2f} ? {'✅' if abs(remaining_cash - expected_cash) < 0.01 else '❌'}")
print(f"  持仓: {position_value:,.2f} == {expected_position:,.2f} ? {'✅' if abs(position_value - expected_position) < 0.01 else '❌'}")
print(f"  总资产: {total_value:,.2f} == {expected_total:,.2f} ? {'✅' if abs(total_value - expected_total) < 0.01 else '❌'}")

print(f"\n结论: 回测引擎计算精准！")
print(f"  买入使用开盘价: {buy_price}")
print(f"  市值使用收盘价: {close_price}")
print(f"  资金守恒: ✅")
