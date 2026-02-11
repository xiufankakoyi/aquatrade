
import requests
import json

def test_sql(sql):
    print(f"\n--- Testing SQL ---\n{sql}")
    r = requests.get('http://localhost:9000/exec', params={'query': sql})
    if r.status_code == 200:
        print("Success!")
        data = r.json()
        print(f"Rows: {len(data.get('dataset', []))}")
        if data.get('dataset'):
            print(json.dumps(data.get('dataset', [])[:1], indent=2))
    else:
        print(f"Failed: {r.text}")

if __name__ == "__main__":
    sql = """
        SELECT 
            s.stock_code,
            to_str(s.trade_date, 'yyyy-MM-dd') AS trade_date,
            m.ma5,
            v.total_mv
        FROM stock_daily s
        LEFT JOIN factors_momentum m ON s.trade_date = m.timestamp AND s.stock_code = m.stock_code
        LEFT JOIN factors_valuation v ON s.trade_date = v.trade_date AND s.stock_code = v.stock_code
        WHERE s.trade_date BETWEEN '2024-05-20' AND '2024-05-21'
            AND s.volume > 0
            AND s.close IS NOT NULL
        ORDER BY 1, 2
        LIMIT 5
    """
    test_sql(sql)
