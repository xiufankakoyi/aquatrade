"""
完整测试数据更新流程
"""
import socketio
import requests
import time

sio = socketio.Client()
received_events = []

@sio.event
def connect():
    print("✅ Socket.IO 已连接")

@sio.event
def disconnect():
    print("❌ Socket.IO 已断开")

@sio.on('db_update_progress')
def on_progress(data):
    print(f"📊 收到进度更新: {data}")
    received_events.append(data)

print("=" * 80)
print("完整测试数据更新流程")
print("=" * 80)

# 1. 连接 Socket.IO
print("\n[1] 连接 Socket.IO...")
try:
    sio.connect('http://localhost:5173', socketio_path='/socket.io', wait_timeout=5)
    print("   连接成功!")
except Exception as e:
    print(f"   连接失败: {e}")
    exit(1)

# 2. 发送更新请求
print("\n[2] 发送更新请求...")
try:
    resp = requests.post('http://localhost:5173/api/db/update', timeout=5)
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"   请求失败: {e}")
    sio.disconnect()
    exit(1)

# 3. 等待接收事件
print("\n[3] 等待接收进度更新 (最多 30 秒)...")
timeout = 30
start = time.time()
while time.time() - start < timeout:
    if len(received_events) > 0 and received_events[-1].get('status') in ['COMPLETED', 'FAILED']:
        break
    time.sleep(0.5)

print(f"\n[4] 测试完成，共收到 {len(received_events)} 个事件:")
for i, event in enumerate(received_events, 1):
    print(f"   {i}. {event.get('status')}: {event.get('message', 'No message')}")

sio.disconnect()
print("\n" + "=" * 80)
