
import time
import lancedb
from pathlib import Path
import pandas as pd
from config.config import Config

def verify_performance():
    print("Checking LanceDB stock_limit_status performance...")
    
    # Setup path
    parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
    lance_dir = str(Path(parquet_dir) / 'lance_db')
    print(f"LanceDB Dir: {lance_dir}")
    
    try:
        db = lancedb.connect(lance_dir)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    table_name = "stock_limit_status"
    if table_name not in db.table_names():
        print(f"Table {table_name} does not exist!")
        return

    table = db.open_table(table_name)
    print(f"Schema: {table.schema}")
    print(f"Rows: {table.count_rows()}")
    
    # Test Query
    start_date = "2024-05-20"
    end_date = "2024-05-25"
    
    print(f"\nQuerying range: {start_date} to {end_date}")
    
    t0 = time.perf_counter()
    
    # Construct query manually as in lance_manager
    where_clause = f"trade_date >= '{start_date}' AND trade_date <= '{end_date}'"
    print(f"Where clause: {where_clause}")
    
    try:
        result = table.search().where(where_clause).to_arrow()
        df = result.to_pandas()
        t1 = time.perf_counter()
        print(f"Query Time: {t1 - t0:.4f}s")
        print(f"Result Rows: {len(df)}")
    except Exception as e:
        print(f"Query failed: {e}")
        
    # Check Indices
    try:
        indices = table.list_indices()
        print(f"\nIndices: {indices}")
    except Exception as e:
        print(f"\nCould not list indices: {e}")

if __name__ == "__main__":
    verify_performance()
