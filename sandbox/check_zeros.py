import duckdb
con = duckdb.connect()
df = con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' WHERE stock_code LIKE '0%' LIMIT 20").df()
print(df)
con.close()
