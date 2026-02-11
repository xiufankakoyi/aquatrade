import duckdb
con = duckdb.connect()
print(con.execute("SELECT DISTINCT trade_date FROM 'parquet_data/stock_daily.parquet' LIMIT 5").df())
con.close()
