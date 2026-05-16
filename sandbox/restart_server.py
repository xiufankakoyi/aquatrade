"""
重启后端服务器脚本
"""
import subprocess
import time
import os
import signal

def kill_existing_server():
    """杀死现有的Python服务器进程"""
    print("[1] 查找并停止现有服务器...")
    try:
        # 查找占用5000端口的进程
        result = subprocess.run(
            ['netstat', '-ano', '|', 'findstr', ':5000'],
            capture_output=True,
            text=True,
            shell=True
        )

        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"    发现进程 PID={pid}，正在终止...")
                        try:
                            os.system(f'taskkill /F /PID {pid}')
                            print(f"    ✅ 已终止进程 {pid}")
                        except Exception as e:
                            print(f"    ⚠️ 终止失败: {e}")

        time.sleep(2)
        print("    ✅ 清理完成")
    except Exception as e:
        print(f"    ⚠️ 清理过程出错: {e}")

def start_server():
    """启动新服务器"""
    print("\n[2] 启动新服务器...")

    # 使用granian启动
    cmd = [
        'granian',
        '--interface', 'asgi',
        '--host', '0.0.0.0',
        '--port', '5000',
        '--workers', '1',
        '--threads', '4',
        '--no-ws',  # 禁用WebSocket
        'server.asgi_entry:app'
    ]

    print(f"    命令: {' '.join(cmd)}")
    print("    服务器启动中...")

    # 在新窗口中启动服务器
    subprocess.Popen(
        cmd,
        cwd='c:\\Users\\Liu\\Desktop\\projects\\aquatrade',
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    # 等待服务器启动
    time.sleep(5)

    # 验证服务器是否启动
    import requests
    try:
        response = requests.get('http://localhost:5000/api/health', timeout=5)
        if response.status_code == 200:
            print("    ✅ 服务器启动成功！")
            return True
    except Exception as e:
        print(f"    ❌ 服务器可能未启动: {e}")
        return False

    return False

if __name__ == "__main__":
    print("=" * 70)
    print("重启后端服务器")
    print("=" * 70)

    kill_existing_server()
    success = start_server()

    if success:
        print("\n" + "=" * 70)
        print("✅ 服务器重启完成！")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ 服务器启动可能失败，请手动检查")
        print("=" * 70)
