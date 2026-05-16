import requests

def query(sql):
    r = requests.get('http://localhost:9000/exec', params={'query': sql})
    return r.json()

tables = ['base_daily', 'factors_momentum', 'factors_valuation']

for table in tables:
    print(f'\n=== {table} ===')
    try:
        result = query(f'SHOW COLUMNS FROM {table}')
        if result.get('dataset'):
            for row in result['dataset']:
                print(f"  {row[0]}: {row[1]}")
    except Exception as e:
        print(f'  Error: {e}')
    
    try:
        count_result = query(f'SELECT COUNT(*) FROM {table}')
        count = count_result.get('dataset', [[0]])[0][0]
        print(f"  数据行数: {count:,}")
    except:
        pass
