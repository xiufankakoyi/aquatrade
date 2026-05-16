"""检查表"""
import requests

# 尝试带引号的表名
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SELECT COUNT(*) FROM "base_daily"'},
    timeout=5
)
print(f'带引号: Status={resp.status_code}')
if resp.status_code == 200:
    print(f'Response: {resp.json()}')
else:
    print(f'Error: {resp.text[:200]}')
