import duckdb
con = duckdb.connect()
print("Data for '2449' in 2024:")
print(con.execute("SELECT * FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '2449' AND trade_date LIKE '2024%' LIMIT 10").df())
con.close()
