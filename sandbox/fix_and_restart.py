"""
修复表结构并重启后端
"""
import subprocess
import time
import requests

print("=" * 70)
print("修复表结构并重启")
print("=" * 70)

# 1. 删除 base_daily 表
print("\n[1] 删除 base_daily 表...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'DROP TABLE IF EXISTS base_daily'},
    timeout=10
)
print(f"   状态: {resp.status_code}")
time.sleep(2)

# 2. 停止后端
print("\n[2] 停止后端...")
subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
print("   ✅ 已停止")
time.sleep(3)

# 3. 启动后端
print("\n[3] 启动后端...")
subprocess.Popen(
    ['start', 'cmd', '/k', 'python', '-m', 'granian', '--interface', 'asgi', 'run:app_asgi', '--port', '5000'],
    shell=True
)
print("   ✅ 启动命令已执行")
print("\n   等待 15 秒...")
time.sleep(15)

# 4. 检查表结构
print("\n[4] 检查新表结构...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': 'SHOW CREATE TABLE base_daily'},
    timeout=5
)
if resp.status_code == 200:
    data = resp.json()
    if 'dataset' in data:
        print(f"   结构: {data['dataset'][0][0]}")

# 5. 测试 ILP
print("\n[5] 测试 ILP 插入...")
import socket

test_line = "base_daily,stock_code=TEST003 open=30.5,high=30.8,low=30.2,close=30.6,volume=3000,amount=15000,adj_factor=1.0,prev_close=30.4 1707004800000000000\n"

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
        params={'query': "SELECT COUNT(*) FROM base_daily WHERE stock_code = 'TEST003'"},
        timeout=5
    )
    data = resp.json()
    if 'dataset' in data:
        count = data['dataset'][0][0]
        print(f"   TEST003 记录数: {count}")
        if count > 0:
            print("   ✅ ILP 正常！")
        else:
            print("   ❌ ILP 失败")
except Exception as e:
    print(f"   错误: {e}")

print("=" * 70)
