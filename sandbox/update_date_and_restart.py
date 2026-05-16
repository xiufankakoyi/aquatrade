"""
更新特定日期数据并重启后端
"""
import subprocess
import time
import os
import signal

print("=" * 80)
print("更新 2026-02-11 数据并重启后端")
print("=" * 80)

# 1. 停止后端服务
print("\n[1] 停止后端服务...")
try:
    # 查找并停止 Python 进程
    result = subprocess.run(
        ['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *granian*'],
        capture_output=True,
        text=True
    )
    print("   已尝试停止后端服务")
    time.sleep(2)
except Exception as e:
    print(f"   停止服务时出错: {e}")

# 2. 更新数据
print("\n[2] 更新 2026-02-11 数据...")
result = subprocess.run(
    ['python', 'sandbox/fetch_specific_date.py'],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.returncode != 0:
    print(f"   错误: {result.stderr}")

# 3. 重启后端服务
print("\n[3] 重启后端服务...")
try:
    # 使用 start 命令在新窗口启动
    subprocess.Popen(
        ['start', 'cmd', '/k', 'python', '-m', 'granian', '--interface', 'asgi', 'run:app_asgi', '--port', '5000'],
        shell=True
    )
    print("   后端服务已启动")
    print("   请等待 10-15 秒让服务完全启动...")
except Exception as e:
    print(f"   启动服务失败: {e}")

print("\n" + "=" * 80)
