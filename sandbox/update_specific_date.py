"""
更新特定日期的数据 (2026-02-11)
"""
import sys
import time
import requests
import socketio
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Socket.IO 客户端
sio = socketio.Client()
received_events = []
completed = False
failed = False

@sio.event
def connect():
    print("✅ Socket.IO 已连接")

@sio.event
def disconnect():
    print("❌ Socket.IO 已断开")

@sio.on('db_update_progress')
def on_progress(data):
    print(f"📊 进度: {data.get('status')} - {data.get('message', '')}")
    received_events.append(data)
    
    if data.get('status') == 'COMPLETED':
        global completed
        completed = True
    elif data.get('status') == 'FAILED':
        global failed
        failed = True

print("=" * 80)
print("更新 2026-02-11 的数据")
print("=" * 80)

# 1. 连接 Socket.IO
print("\n[1] 连接 Socket.IO...")
try:
    sio.connect('http://localhost:5000', socketio_path='/socket.io', wait_timeout=5)
    print("   连接成功!")
except Exception as e:
    print(f"   连接失败: {e}")
    exit(1)

# 2. 检查当前数据库状态
print("\n[2] 检查当前数据库状态...")
try:
    resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
    data = resp.json()
    print(f"   当前最新日期: {data.get('last_date')}")
except Exception as e:
    print(f"   查询失败: {e}")

# 3. 检查缺失日期
print("\n[3] 检查缺失日期...")
try:
    resp = requests.get('http://localhost:5000/api/db/missing_dates', 
                       params={'start_date': '2026-02-11', 'end_date': '2026-02-11'},
                       timeout=5)
    data = resp.json()
    if data.get('success'):
        missing = data.get('missing_dates', [])
        if '20260211' in missing:
            print("   ✅ 2026-02-11 需要更新")
        else:
            print("   ⚠️ 2026-02-11 已存在，无需更新")
    else:
        print(f"   查询失败: {data.get('error')}")
except Exception as e:
    print(f"   查询失败: {e}")

# 4. 发送更新请求
print("\n[4] 发送更新请求...")
try:
    resp = requests.post('http://localhost:5000/api/db/update', timeout=5)
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"   请求失败: {e}")
    sio.disconnect()
    exit(1)

# 5. 等待更新完成
print("\n[5] 等待更新完成 (最多 60 秒)...")
timeout = 60
start = time.time()
while time.time() - start < timeout:
    if completed:
        print("\n✅ 更新成功完成!")
        break
    if failed:
        print("\n❌ 更新失败!")
        break
    time.sleep(0.5)

if not completed and not failed:
    print("\n⏱️ 更新超时")

# 6. 再次检查数据库状态
print("\n[6] 再次检查数据库状态...")
try:
    resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
    data = resp.json()
    print(f"   更新后最新日期: {data.get('last_date')}")
except Exception as e:
    print(f"   查询失败: {e}")

sio.disconnect()

print("\n" + "=" * 80)
print(f"共收到 {len(received_events)} 个进度更新:")
for i, event in enumerate(received_events, 1):
    print(f"  {i}. {event.get('status')}: {event.get('message', 'No message')}")
print("=" * 80)
