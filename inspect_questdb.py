
import requests
import json

def inspect(sql):
    print(f"\n--- {sql} ---")
    r = requests.get('http://localhost:9000/exec', params={'query': sql})
    if r.status_code == 200:
        print(json.dumps(r.json(), indent=2))
    else:
        print(f"Error: {r.text}")

if __name__ == "__main__":
    inspect("tables()")
    inspect("table_columns('base_daily')")
    inspect("table_columns('factors_momentum')")
    inspect("table_columns('factors_valuation')")
