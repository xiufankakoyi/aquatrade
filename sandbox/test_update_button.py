"""
测试数据库更新功能
模拟按下更新按钮的完整流程
"""
import sys
import time
import requests
import socketio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.logger import get_logger

logger = get_logger(__name__)

# Socket.IO 客户端
sio = socketio.Client()

# 状态跟踪
status_updates = []
completed = False
failed = False

@sio.event
def connect():
    print("[Socket.IO] 已连接到服务器")

@sio.event
def disconnect():
    print("[Socket.IO] 已断开连接")

@sio.event
def db_update_progress(data):
    """监听数据库更新进度事件"""
    print(f"\n[Progress] 收到更新: {data}")
    
    status_updates.append(data)
    
    if data.get('status') == 'COMPLETED':
        print("\n✅ 更新成功完成!")
        completed = True
    elif data.get('status') == 'FAILED':
        print(f"\n❌ 更新失败: {data.get('message', '未知错误')}")
        failed = True

def test_update_button():
    """模拟按下更新按钮"""
    print("=" * 80)
    print("测试数据库更新功能")
    print("=" * 80)
    
    # 1. 连接 Socket.IO
    print("\n[1/3] 连接 Socket.IO 服务器...")
    try:
        sio.connect('http://localhost:5000')
        print("✅ Socket.IO 连接成功")
    except Exception as e:
        print(f"❌ Socket.IO 连接失败: {e}")
        return
    
    # 2. 发送更新请求
    print("\n[2/3] 发送数据库更新请求...")
    try:
        resp = requests.post('http://localhost:5000/api/db/update')
        print(f"✅ 更新请求发送成功: {resp.status_code}")
        print(f"响应: {resp.json()}")
    except Exception as e:
        print(f"❌ 更新请求失败: {e}")
        sio.disconnect()
        return
    
    # 3. 等待进度更新
    print("\n[3/3] 等待更新完成 (最多 60 秒)...")
    print("\n进度更新:")
    print("-" * 80)
    
    timeout = 60
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if completed or failed:
            break
        time.sleep(0.5)
    
    # 4. 断开连接
    print("\n" + "=" * 80)
    print("断开连接...")
    sio.disconnect()
    
    # 5. 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"共收到 {len(status_updates)} 个进度更新")
    
    if completed:
        print("✅ 测试通过: 更新成功完成")
    elif failed:
        print("❌ 测试失败: 更新失败")
    else:
        print("⚠️ 测试超时: 60 秒内未完成")
    
    print("\n所有进度更新:")
    for i, update in enumerate(status_updates, 1):
        print(f"  {i}. {update}")

if __name__ == "__main__":
    test_update_button()
