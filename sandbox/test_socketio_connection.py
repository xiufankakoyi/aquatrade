"""
测试 Socket.IO 连接和事件接收
"""
import socketio
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
    print(f"\n📊 收到进度更新: {data}")
    received_events.append(data)

print("=" * 80)
print("测试 Socket.IO 连接")
print("=" * 80)

# 测试连接到前端代理 (5173)
print("\n[1] 连接到前端代理 (http://localhost:5173)...")
try:
    sio.connect('http://localhost:5173', socketio_path='/socket.io', wait_timeout=5)
    print("   连接成功!")
    
    # 等待几秒看是否能收到事件
    print("   等待 5 秒接收事件...")
    time.sleep(5)
    
    print(f"\n   共收到 {len(received_events)} 个事件")
    
    sio.disconnect()
except Exception as e:
    print(f"   连接失败: {e}")

print("\n" + "=" * 80)
