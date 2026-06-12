import duckdb
import sys

p = "data/parquet_data/portfolio_positions.parquet"
escaped = p.replace("'", "''")
connection = duckdb.connect(database=":memory:")
rows = connection.execute(
    f"DESCRIBE SELECT * FROM read_parquet('{escaped}')"
).fetchall()
for row in rows:
    print(row[0], row[1])
