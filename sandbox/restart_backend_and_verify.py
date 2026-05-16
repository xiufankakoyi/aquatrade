"""
重启后端服务器并验证 QuestDB 配置
"""
import subprocess
import time
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
os.chdir(project_root)

# 添加项目根目录到 Python 路径
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 80)
print("重启后端服务器并验证 QuestDB 配置")
print("=" * 80)

# 1. 检查当前配置
print("\n[1] 检查当前配置...")
try:
    from config.config import Config
    print(f"   DB_BACKEND: {Config.DB_BACKEND}")
except Exception as e:
    print(f"   无法加载配置: {e}")
    print("   将继续执行...")

# 2. 停止后端服务
print("\n[2] 停止后端服务...")
try:
    # 查找并停止 Python 进程
    result = subprocess.run(
        ['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *granian*'],
        capture_output=True,
        text=True
    )
    print("   已尝试停止后端服务")
    time.sleep(3)
except Exception as e:
    print(f"   停止服务时出错: {e}")

# 3. 启动后端服务
print("\n[3] 启动后端服务...")
try:
    # 使用 start 命令在新窗口启动
    subprocess.Popen(
        ['start', 'cmd', '/k', 'python', '-m', 'granian', '--interface', 'asgi', 'run:app_asgi', '--port', '5000'],
        shell=True
    )
    print("   ✅ 后端服务已启动")
    print("\n   等待 15 秒让服务完全启动...")
    time.sleep(15)
except Exception as e:
    print(f"   启动服务失败: {e}")
    sys.exit(1)

# 4. 验证后端是否使用 QuestDB
print("\n[4] 验证后端配置...")
import requests
try:
    resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
    data = resp.json()
    print(f"   响应: {data}")
    
    if data.get('success'):
        print(f"   ✅ 后端 API 正常工作")
        print(f"   最后更新日期: {data.get('last_date')}")
    else:
        print(f"   ❌ 后端 API 返回错误")
except Exception as e:
    print(f"   ❌ 连接后端失败: {e}")

# 5. 检查 2026-02-11 数据
print("\n[5] 检查 2026-02-11 数据...")
try:
    resp = requests.get(
        'http://localhost:5000/api/db/missing_dates',
        params={'start_date': '2026-02-11', 'end_date': '2026-02-11'},
        timeout=5
    )
    data = resp.json()
    print(f"   响应: {data}")
    
    if '20260211' in data.get('missing_dates', []):
        print("   ❌ 2026-02-11 仍显示为缺失日期")
    else:
        print("   ✅ 2026-02-11 数据已存在！")
except Exception as e:
    print(f"   ❌ 查询失败: {e}")

print("\n" + "=" * 80)
print("配置完成！")
print("=" * 80)
