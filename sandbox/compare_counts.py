import duckdb
con = duckdb.connect()
print("Count for '2449':")
print(con.execute("SELECT count(*) FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '2449'").df())
print("\nCount for '002449':")
print(con.execute("SELECT count(*) FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '002449'").df())
con.close()
