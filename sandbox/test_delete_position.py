import requests

# 先获取所有持仓
url = 'http://localhost:5000/api/portfolio/positions?active_only=true'
response = requests.get(url)
data = response.json()

print(f"获取持仓状态: {data['success']}")
if data['success']:
    positions = data['data']
    print(f"当前持仓数量: {len(positions)}")
    for p in positions:
        print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")

    # 尝试删除最后一个持仓
    if positions:
        last_id = positions[-1]['id']
        print(f"\n尝试删除 ID={last_id} 的持仓...")

        delete_url = f'http://localhost:5000/api/portfolio/positions/{last_id}'
        delete_response = requests.delete(delete_url)
        print(f"删除响应状态: {delete_response.status_code}")
        print(f"删除响应内容: {delete_response.text}")

        # 验证删除
        print("\n删除后持仓列表:")
        response2 = requests.get(url)
        data2 = response2.json()
        if data2['success']:
            for p in data2['data']:
                print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")
