import duckdb
con = duckdb.connect()
print("Codes matching '2449':")
print(con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '2449'").df())
print("\nCodes matching '002449':")
print(con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '002449'").df())
con.close()
