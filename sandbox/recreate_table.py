"""
重新创建 base_daily 表（不使用 BYPASS WAL）
"""
import requests
import time

print("=" * 70)
print("重新创建 base_daily 表")
print("=" * 70)

# 1. 备份现有数据
print("\n[1] 检查现有数据...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SELECT COUNT(*) FROM base_daily'},
    timeout=5
)
data = resp.json()
if 'dataset' in data:
    count = data['dataset'][0][0]
    print(f"   现有记录数: {count}")

# 2. 删除表
print("\n[2] 删除 base_daily 表...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'DROP TABLE IF EXISTS base_daily'},
    timeout=10
)
print(f"   状态: {resp.status_code}")
time.sleep(2)

# 3. 创建新表（不使用 BYPASS WAL）
print("\n[3] 创建新表...")
create_sql = """
CREATE TABLE base_daily (
    stock_code SYMBOL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    adj_factor DOUBLE,
    prev_close DOUBLE,
    timestamp TIMESTAMP
) TIMESTAMP(timestamp)
"""

resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': create_sql},
    timeout=10
)
print(f"   状态: {resp.status_code}")
if resp.status_code == 200:
    print("   ✅ 表创建成功")
else:
    print(f"   错误: {resp.text[:200]}")
    exit(1)

# 4. 验证表结构
print("\n[4] 验证表结构...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SHOW CREATE TABLE base_daily'},
    timeout=5
)
if resp.status_code == 200:
    data = resp.json()
    if 'dataset' in data:
        print(f"   建表语句: {data['dataset'][0][0][:200]}")

# 5. 测试 ILP 插入
print("\n[5] 测试 ILP 插入...")
import socket

test_line = "base_daily,stock_code=TEST001 open=10.5,high=10.8,low=10.2,close=10.6,volume=1000,amount=5000,adj_factor=1.0,prev_close=10.4 1707004800000000000\n"

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(('localhost', 9009))
    sock.sendall(test_line.encode('utf-8'))
    sock.close()
    print("   ✅ 数据已发送")
    
    time.sleep(3)
    
    resp = requests.get(
        'http://localhost:9000/exec',
        params={'query': "SELECT COUNT(*) FROM base_daily WHERE stock_code = 'TEST001'"},
        timeout=5
    )
    data = resp.json()
    if 'dataset' in data:
        count = data['dataset'][0][0]
        print(f"   TEST001 记录数: {count}")
        if count > 0:
            print("   ✅ ILP 插入成功！")
        else:
            print("   ❌ ILP 插入失败")
            
except Exception as e:
    print(f"   错误: {e}")

print("=" * 70)
