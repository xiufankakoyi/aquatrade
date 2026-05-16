import requests

try:
    r = requests.get('http://localhost:5000/api/strategies', timeout=5)
    print(f'Backend Status: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'Strategies count: {len(data.get("data", []))}')
except requests.exceptions.ConnectionError:
    print('Backend not running - Connection refused')
except requests.exceptions.Timeout:
    print('Backend not responding - Timeout')
except Exception as e:
    print(f'Error: {e}')
