"""检查 Tushare 返回的数据格式"""
import sys
sys.path.insert(0, '.')

import tushare as ts
from config.config import Config

# 设置 token
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取 2025-01-02 的数据
df = pro.daily(trade_date='20250102')

print(f'获取到 {len(df)} 条数据')
print(f'列名: {df.columns.tolist()}')
print()

print('ts_code 示例:')
print(df['ts_code'].head(30).tolist())
print()

# 检查 000036
print('查找 000036:')
result = df[df['ts_code'].str.contains('000036')]
print(f'  包含 000036: {len(result)} 条')
if len(result) > 0:
    print(result[['ts_code', 'open', 'high', 'low', 'close']].to_string())
