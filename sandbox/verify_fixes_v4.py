
import os
import sys
import pandas as pd

# Force QuestDB
os.environ["DB_BACKEND"] = "questdb"

# Ensure project root is in path
sys.path.append(os.getcwd())

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def verify_db():
    print("--- Verifying QuestDB Queries (Forced) ---")
    try:
        query_svc = OptimizedStockDataQuery()
        
        # Test 1: Trading dates preloading
        print("Testing trading dates cache...")
        dates = query_svc._all_trading_dates_cache[:5] if query_svc._all_trading_dates_cache else []
        print(f"Preloaded trading dates: {dates}")
        
        # Test 2: Period data retrieval
        print("\nTesting get_all_daily_data_for_period...")
        df = query_svc.get_all_daily_data_for_period(start_date="2024-05-20", end_date="2024-05-22")
        if df is not None and not df.empty:
            print(f"Successfully retrieved {len(df)} rows of daily data.")
            print(f"Columns: {df.columns.tolist()}")
        else:
            print("Warning: No daily data retrieved.")
            
    except Exception as e:
        print(f"Error during DB verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_db()
