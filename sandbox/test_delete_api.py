import requests
import json

# 先获取当前持仓
resp = requests.get('http://localhost:5000/api/portfolio/positions?active_only=false')
print('当前持仓:')
if resp.json().get('success'):
    positions = resp.json()['data']
    for p in positions:
        print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")
    if positions:
        # 尝试删除第一个
        first_id = positions[0]['id']
        print(f'\n尝试删除 ID={first_id}...')
        del_resp = requests.delete(f'http://localhost:5000/api/portfolio/positions/{first_id}')
        print(f'删除响应: {del_resp.json()}')
        
        # 再次获取确认
        resp2 = requests.get('http://localhost:5000/api/portfolio/positions?active_only=false')
        print(f'\n删除后持仓数量: {len(resp2.json()["data"])}')
else:
    print('获取失败:', resp.json())
