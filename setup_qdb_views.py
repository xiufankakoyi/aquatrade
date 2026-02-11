
import requests

def setup_views():
    queries = [
        "DROP VIEW IF EXISTS stock_daily",
        """
        CREATE VIEW stock_daily AS 
        SELECT 
            timestamp AS trade_date, 
            stock_code, open, high, low, close, volume, amount, adj_factor, prev_close 
        FROM base_daily
        """,
        "DROP VIEW IF EXISTS benchmark_data",
        """
        CREATE VIEW benchmark_data AS 
        SELECT 
            timestamp AS trade_date, 
            stock_code, close, open, high, low, volume, amount
        FROM base_daily 
        WHERE stock_code = '000300.SH'
        """
    ]
    
    for q in queries:
        print(f"Executing: {q[:50]}...")
        r = requests.get('http://localhost:9000/exec', params={'query': q})
        print(f"Result: {r.text}")

if __name__ == "__main__":
    setup_views()
