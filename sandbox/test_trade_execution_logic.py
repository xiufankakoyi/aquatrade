"""
验证交易执行逻辑的正确性

测试两种方法是否产生相同的结果：
1. 原方法：处理整个 stock_pool
2. 新方法：只处理有信号的股票
"""

import pandas as pd
import numpy as np

# 模拟数据
stock_pool = pd.DataFrame({
    'stock_code': ['000001', '000002', '000003', '600000', '600001'],
    'close': [10.0, 20.0, 30.0, 15.0, 25.0],
    'is_limit_up': [0, 1, 0, 0, 0],
    'is_limit_down': [0, 0, 0, 1, 0],
    'is_suspended': [0, 0, 0, 0, 0]
})

signals = {
    '000001': 'buy',   # 正常买入
    '000002': 'buy',   # 涨停，不能买
    '600000': 'sell',  # 跌停，不能卖
    '600001': 'sell',  # 正常卖出
}

print("=" * 60)
print("测试：交易执行逻辑验证")
print("=" * 60)

# 方法1：原方法（处理整个 stock_pool）
print("\n方法1：处理整个 stock_pool")
data_map_old = stock_pool.set_index('stock_code').to_dict('index')
trades_old = []
for code, signal in signals.items():
    if code in data_map_old:
        data = data_map_old[code]
        print(f"  {code}: {signal}, 涨停={data['is_limit_up']}, 跌停={data['is_limit_down']}")
        
        if signal == 'buy' and not data['is_limit_up']:
            trades_old.append(('buy', code))
        elif signal == 'sell' and not data['is_limit_down']:
            trades_old.append(('sell', code))

print(f"结果: {trades_old}")

# 方法2：新方法（只处理有信号的股票）
print("\n方法2：只处理有信号的股票")
signal_codes = set(signals.keys())
signal_pool = stock_pool[stock_pool['stock_code'].isin(signal_codes)]
data_map_new = signal_pool.set_index('stock_code').to_dict('index')
trades_new = []
for code, signal in signals.items():
    if code in data_map_new:
        data = data_map_new[code]
        print(f"  {code}: {signal}, 涨停={data['is_limit_up']}, 跌停={data['is_limit_down']}")
        
        if signal == 'buy' and not data['is_limit_up']:
            trades_new.append(('buy', code))
        elif signal == 'sell' and not data['is_limit_down']:
            trades_new.append(('sell', code))

print(f"结果: {trades_new}")

# 验证
print("\n" + "=" * 60)
if trades_old == trades_new:
    print("✅ 两种方法结果完全相同！优化不会影响交易结果。")
else:
    print("❌ 结果不同！需要检查逻辑。")
    print(f"  方法1: {trades_old}")
    print(f"  方法2: {trades_new}")
print("=" * 60)
