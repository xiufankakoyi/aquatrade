import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from data_svc.database.questdb_manager import get_questdb_manager

def debug_formats():
    print("--- Debugging QuestDB Data ---")
    qdb = get_questdb_manager()
    try:
        # Get 1 row using raw SQL to check format
        df = qdb.query("SELECT * FROM base_daily LIMIT 1")
        print(df)
        if not df.is_empty():
            print("Types:", df.schema)
            print("Timestamp sample:", df[0, "timestamp"])
            print("Code sample:", df[0, "stock_code"])
    except Exception as e:
        print(f"QuestDB Error: {e}")

    print("\n--- Debugging Parquet Data ---")
    try:
        df_pq = pl.read_parquet(r"d:\aquatrade\data\parquet_data\base_daily_archive.parquet", n_rows=1)
        print(df_pq)
        print("Types:", df_pq.schema)
        print("Trade Date sample:", df_pq[0, "trade_date"])
        print("Code sample:", df_pq[0, "stock_code"])
    except Exception as e:
        print(f"Parquet Error: {e}")

if __name__ == "__main__":
    debug_formats()
