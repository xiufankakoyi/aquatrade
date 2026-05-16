"""
检查 base_daily 表的问题
"""
import socket
import requests
import time

print("=" * 70)
print("检查 base_daily 表问题")
print("=" * 70)

# 1. 检查表是否存在
print("\n[1] 检查表是否存在...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SHOW TABLES"},
    timeout=5
)
data = resp.json()
if 'dataset' in data:
    tables = [row[0] for row in data['dataset']]
    print(f"   所有表: {tables}")
    if 'base_daily' in tables:
        print("   ✅ base_daily 表存在")
    else:
        print("   ❌ base_daily 表不存在")

# 2. 检查表结构
print("\n[2] 检查表结构...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SELECT * FROM base_daily LIMIT 0'},
    timeout=5
)
data = resp.json()
if 'columns' in data:
    print("   列信息:")
    for col in data['columns']:
        print(f"     {col['name']}: {col['type']}")

# 3. 检查表是否可写
print("\n[3] 测试向 base_daily 插入数据...")
test_line = "base_daily,stock_code=TEST999 open=10.5,high=10.8,low=10.2,close=10.6,volume=1000,amount=5000,adj_factor=1.0,prev_close=10.4 1707004800000000000\n"

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(('localhost', 9009))
    sock.sendall(test_line.encode('utf-8'))
    sock.close()
    print("   ✅ 数据已发送")
    
    # 等待
    time.sleep(3)
    
    # 检查
    resp = requests.get(
        'http://localhost:9000/exec',
        params={'query': "SELECT COUNT(*) FROM base_daily WHERE stock_code = 'TEST999'"},
        timeout=5
    )
    data = resp.json()
    if 'dataset' in data:
        count = data['dataset'][0][0]
        print(f"   TEST999 记录数: {count}")
        if count > 0:
            print("   ✅ 插入成功！")
        else:
            print("   ❌ 插入失败！")
            
except Exception as e:
    print(f"   错误: {e}")

# 4. 检查表属性
print("\n[4] 检查表属性...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SHOW CREATE TABLE base_daily"},
    timeout=5
)
print(f"   状态: {resp.status_code}")
if resp.status_code == 200:
    print(f"   响应: {resp.text[:500]}")

# 5. 检查是否有锁
print("\n[5] 检查表锁定状态...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT * FROM information_schema.tables WHERE table_name = 'base_daily'"},
    timeout=5
)
print(f"   状态: {resp.status_code}")
if resp.status_code == 200:
    print(f"   响应: {resp.text[:500]}")

print("=" * 70)
