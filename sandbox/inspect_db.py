import duckdb
import pandas as pd
con = duckdb.connect()
df = con.execute("SELECT DISTINCT stock_code FROM 'parquet_data/stock_daily.parquet' LIMIT 20").df()
print(df)
con.close()
