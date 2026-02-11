
import requests
import time

def test_sql(sql):
    print(f"\n--- Testing SQL ---\n{sql}")
    t0 = time.perf_counter()
    r = requests.get('http://localhost:9000/exec', params={'query': sql})
    elapsed = time.perf_counter() - t0
    print(f"Time taken: {elapsed:.3f}s")
    if r.status_code == 200:
        data = r.json()
        print(f"Success! Rows: {len(data.get('dataset', []))}")
    else:
        print(f"Failed: {r.text}")

if __name__ == "__main__":
    sql = """
        SELECT 
            s.stock_code,
            to_str(s.trade_date, 'yyyy-MM-dd') AS trade_date,
            s.open, s.high, s.low, s.close, s.prev_close, s.volume, s.amount, s.adj_factor,
            m.ma5, m.ma10, m.ma20, m.ma60,
            v.total_mv, v.float_mv, v.turnover_rate, v.turnover_free, v.volume_ratio
        FROM stock_daily s
        LEFT JOIN factors_momentum m ON s.trade_date = m.timestamp AND s.stock_code = m.stock_code
        LEFT JOIN factors_valuation v ON s.trade_date = v.trade_date AND s.stock_code = v.stock_code
        WHERE s.trade_date BETWEEN '2024-05-20' AND '2024-05-22'
            AND s.volume > 0
            AND s.close IS NOT NULL
        ORDER BY 1, 2
    """
    test_sql(sql)
