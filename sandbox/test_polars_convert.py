"""测试 Polars 转换"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import polars as pl
import tushare as ts
from config.config import Config

# 设置 token
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

# 获取 2025-01-02 的数据
df = pro.daily(trade_date='20250102')

# 执行 standardize_stock_columns 的逻辑
df['stock_code'] = df['ts_code'].str.split('.', expand=True)[0]
df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')

print(f'Pandas stock_code 类型: {df["stock_code"].dtype}')
print(f'Pandas stock_code 示例: {df["stock_code"].head(10).tolist()}')
print()

# 转换为 Polars
df_pl = pl.from_pandas(df)

print(f'Polars stock_code 类型: {df_pl["stock_code"].dtype}')
print(f'Polars stock_code 示例: {df_pl["stock_code"].head(10).to_list()}')
print()

# 查找 000036
result = df_pl.filter(pl.col('ts_code').str.contains('000036'))
print(f'Polars 中 ts_code 包含 000036:')
print(result.select(['ts_code', 'stock_code']).to_pandas().to_string())
print()

result2 = df_pl.filter(pl.col('stock_code') == '000036')
print(f'Polars 中 stock_code = 000036: {len(result2)} 条')

result3 = df_pl.filter(pl.col('stock_code') == '36')
print(f'Polars 中 stock_code = 36: {len(result3)} 条')
