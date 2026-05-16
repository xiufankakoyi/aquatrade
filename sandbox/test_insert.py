"""测试插入"""
import requests

# 检查表结构
resp = requests.get('http://localhost:9000/exec', params={'query': 'SHOW CREATE TABLE base_daily'}, timeout=5)
data = resp.json()
if 'dataset' in data:
    print('表结构:', data['dataset'][0][0])

# 测试插入
insert_sql = "INSERT INTO base_daily (stock_code, open, high, low, close, volume, amount, adj_factor, prev_close, timestamp) VALUES ('000001', 10.5, 10.8, 10.2, 10.6, 1000, 5000, 1.0, 10.4, '2026-02-04T00:00:00.000000Z')"

resp = requests.get('http://localhost:9000/exec', params={'query': insert_sql}, timeout=10)
print(f'插入: {resp.status_code}')
if resp.status_code != 200:
    print(f'错误: {resp.text}')
else:
    print('✅ 插入成功')
    
    # 验证
    resp = requests.get('http://localhost:9000/exec', params={'query': 'SELECT COUNT(*) FROM base_daily'}, timeout=5)
    data = resp.json()
    if 'dataset' in data:
        print(f'记录数: {data["dataset"][0][0]}')
