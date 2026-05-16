import requests

r = requests.get('http://localhost:5000/api/kline?symbol=000300&start=2024-01-01&end=2025-12-31')
print('Status:', r.status_code)
print('Type:', type(r.json()))
print('Content:', r.text[:500])
