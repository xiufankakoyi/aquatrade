"""检查 Parquet 文件中的 ts_code 列"""
import polars as pl

# 读取 Parquet 文件
df = pl.read_parquet('data/parquet_data/stock_daily.parquet')

print(f'总行数: {len(df)}')
print(f'列名: {df.columns}')
print()

# 检查是否有 ts_code 列
if 'ts_code' in df.columns:
    print('ts_code 列存在')
    # 过滤 2025-01-02 的数据
    df_0102 = df.filter(pl.col('trade_date') == '2025-01-02')
    print(f'2025-01-02 的股票数: {len(df_0102)}')
    
    # 检查 ts_code 格式
    ts_codes = df_0102['ts_code'].unique().to_list()
    print(f'ts_code 示例: {ts_codes[:20]}')
    
    # 统计各板块
    sz_count = sum(1 for c in ts_codes if '.SZ' in str(c))
    sh_count = sum(1 for c in ts_codes if '.SH' in str(c))
    
    print(f'\n深市股票(.SZ): {sz_count}')
    print(f'沪市股票(.SH): {sh_count}')
else:
    print('ts_code 列不存在')
    print('stock_code 示例:')
    df_0102 = df.filter(pl.col('trade_date') == '2025-01-02')
    codes = df_0102['stock_code'].unique().to_list()
    print(codes[:20])
