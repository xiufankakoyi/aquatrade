"""
检查 QuestDB 状态并修复
"""
import requests
import socket
import time

print("=" * 70)
print("检查 QuestDB 状态")
print("=" * 70)

# 1. 检查表是否存在
print("\n[1] 检查表...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SHOW TABLES'},
    timeout=5
)
data = resp.json()
if 'dataset' in data:
    tables = [row[0] for row in data['dataset']]
    print(f"   表: {tables}")

# 2. 检查 base_daily 结构
print("\n[2] 检查 base_daily...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SHOW CREATE TABLE base_daily'},
    timeout=5
)
if resp.status_code == 200:
    data = resp.json()
    if 'dataset' in data:
        print(f"   结构: {data['dataset'][0][0][:150]}")
else:
    print(f"   错误: {resp.status_code}")

# 3. 测试 ILP 插入
print("\n[3] 测试 ILP 插入...")
test_line = "base_daily,stock_code=TEST002 open=20.5,high=20.8,low=20.2,close=20.6,volume=2000,amount=10000,adj_factor=1.0,prev_close=20.4 1706918400000000000\n"

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(('localhost', 9009))
    sock.sendall(test_line.encode('utf-8'))
    sock.close()
    print("   ✅ 已发送")
    
    time.sleep(3)
    
    resp = requests.get(
        'http://localhost:9000/exec',
        params={'query': "SELECT COUNT(*) FROM base_daily WHERE stock_code = 'TEST002'"},
        timeout=5
    )
    data = resp.json()
    if 'dataset' in data:
        count = data['dataset'][0][0]
        print(f"   TEST002 记录数: {count}")
        if count > 0:
            print("   ✅ ILP 正常")
        else:
            print("   ❌ ILP 失败，需要重建表")
except Exception as e:
    print(f"   错误: {e}")

# 4. 检查 2026-02-04 的数据
print("\n[4] 检查 2026-02-04 数据...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT COUNT(*) FROM base_daily WHERE date_trunc('day', timestamp) = '2026-02-04'"},
    timeout=5
)
if 'dataset' in data:
    count = data['dataset'][0][0]
    print(f"   2026-02-04: {count} 条")

print("=" * 70)
