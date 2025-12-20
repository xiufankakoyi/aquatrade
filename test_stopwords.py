import duckdb
from pathlib import Path

p = Path("parquet_data") / "stock_daily.parquet"
print(p, p.exists())

con = duckdb.connect()
parquet_str = str(p).replace("\\", "/")

# 1. 看所有列和类型
print(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet_str}')").fetchall())

# 2. 看前几行数据
print(con.execute(f"SELECT * FROM read_parquet('{parquet_str}') LIMIT 5").fetch_df())


p_info = Path("parquet_data") / "stock_info.parquet"
info_str = str(p_info).replace("\\", "/")

print(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{info_str}')").fetchall())
print(con.execute(f"SELECT * FROM read_parquet('{info_str}') LIMIT 5").fetch_df())
