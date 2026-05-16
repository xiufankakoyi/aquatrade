"""测试 standardize_stock_columns 方法"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import tushare as ts
from config.config import Config

# 设置 token
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取 2025-01-02 的数据
df = pro.daily(trade_date='20250102')

print(f'原始数据: {len(df)} 条')
print(f'原始 ts_code 类型: {df["ts_code"].dtype}')
print(f'原始 ts_code 示例: {df["ts_code"].head(10).tolist()}')
print()

# 执行 standardize_stock_columns 的逻辑
df['stock_code'] = df['ts_code'].str.split('.', expand=True)[0]
df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

print(f'处理后 stock_code 类型: {df["stock_code"].dtype}')
print(f'处理后 stock_code 示例: {df["stock_code"].head(10).tolist()}')
print()

# 查找 000036
print('查找 000036:')
result = df[df['ts_code'].str.contains('000036')]
print(f'  ts_code 包含 000036:')
print(result[['ts_code', 'stock_code']].to_string())

result2 = df[df['stock_code'] == '000036']
print(f'  stock_code = 000036: {len(result2)} 条')

result3 = df[df['stock_code'] == '36']
print(f'  stock_code = 36: {len(result3)} 条')
