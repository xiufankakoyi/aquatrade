"""检查后端配置"""
import requests

print('检查后端配置...')
resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
data = resp.json()
print(f"最后日期: {data.get('last_date')}")
print(f"消息: {data.get('message')}")

print('\n检查缺失日期...')
resp = requests.get(
    'http://localhost:5000/api/db/missing_dates',
    params={'start_date': '2026-02-04', 'end_date': '2026-02-14'},
    timeout=5
)
data = resp.json()
print(f"缺失日期: {data.get('missing_dates', [])}")
