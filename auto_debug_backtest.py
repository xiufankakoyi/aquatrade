"""
自动启动前端并运行 Playwright 调试脚本
"""
import subprocess
import time
import os
import sys
from pathlib import Path

def start_frontend():
    """启动前端开发服务器"""
    myapp_dir = Path('myapp')
    if not myapp_dir.exists():
        print("❌ 错误: myapp 目录不存在")
        return None
    
    print("🚀 启动前端开发服务器...")
    # 使用新的控制台窗口启动前端，这样不会阻塞
    process = subprocess.Popen(
        ['npm', 'run', 'dev'],
        cwd=str(myapp_dir),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    
    # 等待前端启动
    print("⏳ 等待前端服务器启动...")
    for i in range(30):  # 最多等待30秒
        time.sleep(1)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 5173))
            sock.close()
            if result == 0:
                print("✅ 前端服务器已启动 (http://localhost:5173)")
                return process
        except:
            pass
        if i % 5 == 0:
            print(f"   等待中... ({i+1}/30)")
    
    print("⚠️  前端服务器可能未完全启动，但继续执行...")
    return process

if __name__ == "__main__":
    print("=" * 60)
    print("自动调试回测问题")
    print("=" * 60)
    
    # 启动前端
    frontend_process = start_frontend()
    
    if frontend_process:
        # 等待一下确保前端完全启动
        time.sleep(3)
        
        # 运行 Playwright 调试脚本
        print("\n" + "=" * 60)
        print("启动 Playwright 调试脚本...")
        print("=" * 60 + "\n")
        
        import debug_backtest_playwright
        import asyncio
        asyncio.run(debug_backtest_playwright.run_backtest_debug())
        
        # 清理：不关闭前端，让用户继续使用
        print("\n" + "=" * 60)
        print("调试完成")
        print("=" * 60)
        print("前端服务器仍在运行，您可以继续使用")
        print("要停止前端服务器，请关闭对应的控制台窗口")
    else:
        print("❌ 无法启动前端服务器")
