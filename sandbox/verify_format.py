import duckdb
con = duckdb.connect()
print("Codes matching '498':")
print(con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '498'").df())
print("\nCodes matching '000498':")
print(con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' WHERE stock_code = '000498'").df())
con.close()
