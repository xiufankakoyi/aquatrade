"""
系统工具函数模块
提供系统相关的工具函数，如重启管理等
"""
import os
import sys
import threading
import time

# 重启管理相关的全局变量
_restart_lock = threading.Lock()
_restart_scheduled = False


def _schedule_restart(delay: float = 1.0) -> None:
    """
    在单独的线程里延迟执行 os.execl，实现平滑重启。
    """
    global _restart_scheduled
    with _restart_lock:
        if _restart_scheduled:
            return
        _restart_scheduled = True

    def _restart():
        time.sleep(delay)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    threading.Thread(target=_restart, daemon=True).start()

