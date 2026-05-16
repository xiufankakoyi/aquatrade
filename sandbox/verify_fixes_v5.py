
import os
import sys
import pandas as pd
import logging

# Force QuestDB
os.environ["DB_BACKEND"] = "questdb"

# Ensure project root is in path
sys.path.append(os.getcwd())

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def verify_db():
    print("--- Verifying QuestDB Queries (Debug) ---")
    try:
        query_svc = OptimizedStockDataQuery()
        
        print(f"Backend set to QuestDB: {query_svc._use_questdb}")
        
        # Test SQL directly
        print("\nTesting Query directly via QuestDBManager...")
        sql = "SELECT DISTINCT timestamp FROM base_daily LIMIT 10"
        try:
            df_pl = query_svc.questdb_manager.query(sql)
            print(f"Direct Query result: {len(df_pl)} rows")
            if not df_pl.is_empty():
                print(f"Data: {df_pl.head(2)}")
        except Exception as e:
            print(f"Direct Query FAILED: {e}")

        # Test join query
        print("\nTesting Join Query directly...")
        sql = """
            SELECT 
                b.stock_code,
                to_str(b.timestamp, 'yyyy-MM-dd') AS trade_date,
                m.ma5
            FROM base_daily b
            LEFT JOIN factors_momentum m ON b.timestamp = m.timestamp AND b.stock_code = m.stock_code
            LIMIT 5
        """
        try:
            df_pl = query_svc.questdb_manager.query(sql)
            print(f"Join Query result: {len(df_pl)} rows")
        except Exception as e:
            print(f"Join Query FAILED: {e}")

    except Exception as e:
        print(f"Error during DB verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_db()
