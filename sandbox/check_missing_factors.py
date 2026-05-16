import polars as pl

factor_df = pl.scan_parquet('data/parquet_data/factors_momentum_hot.parquet').collect()

# 检查上海贝岭
beiling = factor_df.filter(pl.col('stock_code') == '600171')
print('上海贝岭因子数据:')
print(f'  总行数: {len(beiling)}')
print(f'  beta_60d 非空: {len(beiling) - beiling["beta_60d"].null_count()} / {len(beiling)}')
print()

# 检查最新数据
latest = beiling.sort('trade_date', descending=True).head(5)
print('最新5天数据:')
print(latest.select(['trade_date', 'stock_code', 'beta_60d', 'alpha_60d', 'corr_60d', 'return_5d']))
