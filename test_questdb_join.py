
import requests
import json

def test_sql(sql):
    print(f"\n--- Testing SQL ---\n{sql}")
    r = requests.get('http://localhost:9000/exec', params={'query': sql})
    if r.status_code == 200:
        print("Success!")
        print(json.dumps(r.json().get('dataset', [])[:1], indent=2))
    else:
        print(f"Failed: {r.text}")

if __name__ == "__main__":
    sql = """
        SELECT b.stock_code, b.timestamp, m.ma5
        FROM base_daily b
        LEFT JOIN factors_momentum m ON b.timestamp = m.timestamp AND b.stock_code = m.stock_code
        LIMIT 1
    """
    # Try with b. prefix first
    test_sql(sql)
    
    # Try without b. prefix if it fails
    sql2 = """
        SELECT base_daily.stock_code, base_daily.timestamp, factors_momentum.ma5
        FROM base_daily
        LEFT JOIN factors_momentum ON base_daily.timestamp = factors_momentum.timestamp AND base_daily.stock_code = factors_momentum.stock_code
        LIMIT 1
    """
    test_sql(sql2)
