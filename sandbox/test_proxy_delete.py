"""
测试前端代理是否正确转发 DELETE 请求
"""
import requests

# 通过前端代理发送请求
PROXY_URL = 'http://localhost:5173'

print("=== 通过前端代理测试 ===")
resp = requests.get(f'{PROXY_URL}/api/portfolio/positions?active_only=false')
print(f"GET 状态码: {resp.status_code}")
data = resp.json()
positions = data.get('data', [])
print(f"持仓数量: {len(positions)}")

if positions:
    target_id = positions[0]['id']
    print(f"\n尝试删除 ID={target_id}")
    
    # 通过代理发送 DELETE 请求
    del_resp = requests.delete(f'{PROXY_URL}/api/portfolio/positions/{target_id}')
    print(f"DELETE 状态码: {del_resp.status_code}")
    print(f"DELETE 响应: {del_resp.text[:500]}")
