# server/asgi_entry.py
"""
ASGI 入口点 - 使用 python-socketio AsyncServer

解决 Flask-SocketIO 与 ASGI 不兼容的问题
使用原生 python-socketio 的 AsyncServer 以获得完整的 ASGI 支持
"""
import os
import sys
import warnings
from pathlib import Path

# 忽略 asgiref.wsgi 中的非异步标注警告
warnings.filterwarnings(
    "ignore", 
    message="async_to_sync was passed a non-async-marked callable", 
    module="asgiref.wsgi"
)

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 关键：先设置环境变量，避免 Flask-SocketIO 初始化错误
os.environ['USE_GRANIAN'] = 'true'

# 导入 Flask 应用（包含所有路由和 CORS 配置）
from server.app import app as flask_app

# 创建异步 SocketIO 服务器
import socketio

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False,
    ping_interval=25000,
    ping_timeout=60000
)

# 导入 SocketIO 事件处理器
print("\n" + "="*80)
print("[ASGI] Importing asgi_socketio_handlers...")
try:
    from server.asgi_socketio_handlers import register_handlers
    print("[ASGI] Calling register_handlers(sio)...")
    register_handlers(sio)
    print("[ASGI] OK - Socket.IO event handlers registered!")
except Exception as e:
    print(f"[ASGI] ERROR - Failed to register Socket.IO handlers: {e}")
    import traceback
    traceback.print_exc()
    raise
print("="*80 + "\n")

# 将 Flask 应用包装成 ASGI 应用
from asgiref.wsgi import WsgiToAsgi
flask_asgi_app = WsgiToAsgi(flask_app)

# 创建 ASGIApp，将 SocketIO 和 Flask 组合
app_asgi = socketio.ASGIApp(sio, other_asgi_app=flask_asgi_app, socketio_path='socket.io')

# 启动文件监听器（热重载）
try:
    from core.strategies.hot_reload import get_watcher
    watcher = get_watcher()
    watcher.start()
    print("[OK] Strategy file watcher started (Hot-reload enabled)")
except Exception as e:
    print(f"[WARNING] File watcher startup failed: {e}")

# 导出给 Granian 使用
asgi_app = app_asgi
