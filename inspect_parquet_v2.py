
import duckdb
import os

parquet_dir = r"d:\aquatrade\data\parquet_data"
files = ["stock_daily.parquet", "benchmark_daily.parquet", "guba_posts.parquet"]

for filename in files:
    pf = os.path.join(parquet_dir, filename)
    if not os.path.exists(pf):
        print(f"File not found: {filename}")
        continue
    
    print(f"\n=== {filename} ===")
    try:
        con = duckdb.connect()
        columns = con.execute(f"DESCRIBE SELECT * FROM '{pf}' LIMIT 0").fetchall()
        col_names = [col[0] for col in columns]
        # Print columns in groups of 5 to avoid horizontal truncation
        for i in range(0, len(col_names), 5):
            print(", ".join(col_names[i:i+5]))
    except Exception as e:
        print(f"Error reading {filename}: {e}")
