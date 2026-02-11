
import duckdb
import os

parquet_dir = r"d:\aquatrade\data\parquet_data"
files = ["stock_daily.parquet", "benchmark_daily.parquet", "guba_posts.parquet", "stock_info.parquet", "stock_limit_status.parquet"]

for filename in files:
    pf = os.path.join(parquet_dir, filename)
    if not os.path.exists(pf):
        print(f"File not found: {filename}")
        continue
    
    print(f"\nSTART_SCHEMA: {filename}")
    try:
        con = duckdb.connect()
        columns = con.execute(f"DESCRIBE SELECT * FROM '{pf}' LIMIT 0").fetchall()
        for col in columns:
            print(f"COL: {col[0]}")
    except Exception as e:
        print(f"Error reading {filename}: {e}")
    print(f"END_SCHEMA: {filename}")
