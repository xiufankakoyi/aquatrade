import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager
from datetime import datetime

def test_unified_data_manager():
    print("Initializing UnifiedDataManager...")
    udm = UnifiedDataManager()
    
    # Test stock that definitely has data (based on DB probe)
    test_code = "600808.SH" 

    # Test 1: Cold Data (Pre-2020)
    print(f"\n--- Test 1: Cold Data (2019-01-01 to 2019-01-10) for {test_code} ---")
    df_cold = udm.get_price(
        codes=[test_code], 
        start_date="2019-01-01", 
        end_date="2019-01-10"
    )
    print(df_cold)
    print(f"Rows: {len(df_cold)}")
    
    if len(df_cold) > 0:
        print(f"✅ Cold Data OK (Transparently handled '{test_code}')")
    else:
        print("❌ Cold Data Failed (Data might be missing for this period)")

    # Test 2: Hot Data (Post-2020)
    print(f"\n--- Test 2: Hot Data (2021-01-01 to 2021-01-10) for {test_code} ---")
    df_hot = udm.get_price(
        codes=[test_code], 
        start_date="2021-01-01", 
        end_date="2021-01-10"
    )
    print(df_hot)
    print(f"Rows: {len(df_hot)}")
    
    if len(df_hot) > 0:
        print(f"✅ Hot Data OK (Transparently handled '{test_code}')")
    else:
        print("❌ Hot Data Failed")

    # Test 3: Hybrid Data (Crossing 2020-01-01)
    print(f"\n--- Test 3: Hybrid Data (2019-12-25 to 2020-01-05) for {test_code} ---")
    df_hybrid = udm.get_price(
        codes=[test_code], 
        start_date="2019-12-25", 
        end_date="2020-01-05"
    )
    print(df_hybrid)
    print(f"Rows: {len(df_hybrid)}")
    
    if len(df_hybrid) > 0:
        min_date = df_hybrid["ts"].min()
        max_date = df_hybrid["ts"].max()
        print(f"Date Range: {min_date} to {max_date}")
        
        # Check if we have both 2019 and 2020 dates
        has_2019 = any(str(d).startswith("2019") for d in df_hybrid["ts"])
        has_2020 = any(str(d).startswith("2020") for d in df_hybrid["ts"])
        
        if has_2019 and has_2020:
            print("✅ Hybrid Data OK (Contains both 2019 and 2020)")
        else:
            print(f"❌ Hybrid Data Incomplete ({test_code}) (Has 2019: {has_2019}, Has 2020: {has_2020})")
    else:
        print("⚠️ No Hybrid Data Found")

if __name__ == "__main__":
    test_unified_data_manager()
