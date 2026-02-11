
import duckdb
import os
import glob

parquet_dir = r"d:\aquatrade\data\parquet_data"
parquet_files = glob.glob(os.path.join(parquet_dir, "*.parquet"))

print(f"Checking parquet files in: {parquet_dir}")
for pf in parquet_files:
    filename = os.path.basename(pf)
    try:
        con = duckdb.connect()
        columns = con.execute(f"DESCRIBE SELECT * FROM '{pf}' LIMIT 0").fetchall()
        col_names = [col[0] for col in columns]
        print(", ".join(col_names))
    except Exception as e:
        print(f"Error reading {filename}: {e}")
