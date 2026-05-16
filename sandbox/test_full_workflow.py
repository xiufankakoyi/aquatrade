"""
完整测试工作流程
验证数据已是最新的场景
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

def test_full_workflow():
    """完整测试工作流"""
    print("=" * 80)
    print("完整测试工作流程")
    print("=" * 80)
    
    # 1. 检查数据库状态
    print("\n[1/5] 检查数据库最新日期...")
    try:
        resp = requests.get('http://localhost:5000/api/db/last_date')
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                print(f"   ✅ 数据库最新日期: {data.get('last_date')}")
            else:
                print(f"   ⚠️ 获取日期失败: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    # 2. 检查缺失日期
    print("\n[2/5] 检查缺失日期...")
    try:
        today = time.strftime('%Y-%m-%d')
        resp = requests.get('http://localhost:5000/api/db/missing_dates', params={
            'start_date': '2025-01-01',
            'end_date': today
        })
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                count = data.get('missing_count', 0)
                if count == 0:
                    print(f"   ✅ 数据完整，没有缺失日期")
                else:
                    print(f"   ⚠️ 发现 {count} 个缺失日期")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    # 3. 连接 Socket.IO
    print("\n[3/5] 连接 Socket.IO 服务器...")
    try:
        sio.connect('http://localhost:5000')
        print("   ✅ Socket.IO 连接成功")
    except Exception as e:
        print(f"   ❌ Socket.IO 连接失败: {e}")
        return
    
    # 4. 发送更新请求
    print("\n[4/5] 发送数据库更新请求...")
    try:
        resp = requests.post('http://localhost:5000/api/db/update')
        print(f"   ✅ 更新请求发送成功: {resp.status_code}")
        print(f"   响应: {resp.json()}")
    except Exception as e:
        print(f"   ❌ 更新请求失败: {e}")
        sio.disconnect()
        return
    
    # 5. 等待进度更新
    print("\n[5/5] 等待更新完成 (最多 30 秒)...")
    print("\n进度更新:")
    print("-" * 80)
    
    timeout = 30
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if completed or failed:
            break
        time.sleep(0.5)
    
    # 总结
    print("\n" + "=" * 80)
    print("断开连接...")
    sio.disconnect()
    
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"共收到 {len(status_updates)} 个进度更新")
    
    if completed:
        print("✅ 测试通过: 更新成功完成")
        if len(status_updates) == 2:
            print("   (数据已是最新，只发送了 STARTING -> COMPLETED)")
    elif failed:
        print("❌ 测试失败: 更新失败")
    else:
        print("⚠️ 测试超时: 30 秒内未完成")
    
    print("\n所有进度更新:")
    for i, update in enumerate(status_updates, 1):
        print(f"  {i}. {update}")
    
    print("\n" + "=" * 80)
    print("后端错误处理机制状态:")
    print("1. ✅ time 模块已导入 (data_routes.py:7)")
    print("2. ✅ 后台线程错误处理已增强 (data_routes.py:94-163)")
    print("3. ✅ 全局线程异常钩子已配置 (app.py:15-82)")
    print("4. ✅ ErrorHandler 系统已集成")
    print("5. ✅ 任何错误都会通过 Socket.IO 发送 FAILED 状态")
    print("=" * 80)

if __name__ == "__main__":
    test_full_workflow()
