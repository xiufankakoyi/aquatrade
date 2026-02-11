import duckdb
con = duckdb.connect()
df = con.execute("DESCRIBE SELECT * FROM 'parquet_data/stock_daily.parquet'").df()
print(df[df['column_name'].isin(['stock_code', 'trade_date', 'ts_code'])][['column_name', 'column_type']])
con.close()
