"""
调试 ILP 插入问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import socket
import requests
import pandas as pd
from config.config import Config

print("=" * 70)
print("调试 ILP 插入")
print("=" * 70)

# 1. 检查表结构
print("\n[1] 检查 QuestDB 表结构...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SELECT * FROM base_daily LIMIT 0'},
    timeout=5
)
data = resp.json()
if 'columns' in data:
    print("表结构:")
    for col in data['columns']:
        print(f"  - {col['name']}: {col['type']}")

# 2. 检查现有数据
print("\n[2] 检查现有数据...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SELECT COUNT(*) FROM base_daily'},
    timeout=5
)
data = resp.json()
if 'dataset' in data:
    print(f"总记录数: {data['dataset'][0][0]}")

# 3. 尝试插入一条测试数据
print("\n[3] 尝试插入一条测试数据...")

# 构建一条简单的 ILP 记录
# 注意：symbol 字段在 ILP 中不需要引号
test_line = "base_daily,stock_code=TEST001 open=10.5,high=10.8,low=10.2,close=10.6,volume=1000,amount=5000,adj_factor=1.0,prev_close=10.4 1707004800000000000\n"

print(f"ILP 数据: {test_line.strip()}")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(('localhost', 9009))
    sock.sendall(test_line.encode('utf-8'))
    
    # 尝试接收响应
    try:
        response = sock.recv(1024)
        print(f"响应: {response.decode('utf-8')}")
    except socket.timeout:
        print("没有收到响应（正常情况）")
    
    sock.close()
    print("✅ 数据已发送")
    
except Exception as e:
    print(f"❌ 发送失败: {e}")

# 4. 等待并验证
print("\n[4] 等待 5 秒后验证...")
import time
time.sleep(5)

resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT COUNT(*) FROM base_daily WHERE stock_code = 'TEST001'"},
    timeout=5
)
data = resp.json()
if 'dataset' in data:
    count = data['dataset'][0][0]
    print(f"TEST001 记录数: {count}")
    if count > 0:
        print("✅ 测试数据插入成功！")
    else:
        print("❌ 测试数据未找到")

print("=" * 70)
