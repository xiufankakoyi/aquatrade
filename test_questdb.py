
import os
import requests
import json

QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_HTTP_PORT = int(os.getenv("QUESTDB_HTTP_PORT", "9000"))

def test_query(description, sql):
    print(f"\n--- Testing: {description} ---")
    print(f"SQL: {sql}")
    try:
        resp = requests.get(
            f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec",
            params={"query": sql}
        )
        if resp.status_code == 200:
            print("Status: SUCCESS")
            data = resp.json()
            print(f"Rows: {len(data.get('dataset', []))}")
            if data.get('dataset'):
                print(f"First row: {data['dataset'][0]}")
        else:
            print(f"Status: FAILED")
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test 1: Simple select with alias
    test_query("Simple select with alias", "SELECT b.code, b.ts FROM base_daily b LIMIT 1")
    
    # Test 2: Join with ON and aliases
    test_query("Join with ON and aliases", 
               "SELECT b.code, b.ts, m.ma5 FROM base_daily b LEFT JOIN factors_momentum m ON b.ts = m.ts AND b.code = m.code LIMIT 1")
    
    # Test 3: Join with full table names
    test_query("Join with full table names", 
               "SELECT base_daily.code, base_daily.ts, factors_momentum.ma5 FROM base_daily LEFT JOIN factors_momentum ON base_daily.ts = factors_momentum.ts AND base_daily.code = factors_momentum.code LIMIT 1")

    # Test 4: Check if stock_daily exists
    test_query("Check stock_daily", "SELECT * FROM stock_daily LIMIT 1")
    
    # Test 5: Check base_daily DISTINCT
    test_query("Check base_daily DISTINCT", "SELECT DISTINCT code FROM base_daily LIMIT 5")
