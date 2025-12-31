# server/asgi_entry.py
"""
ASGI 入口点 - 使用 python-socketio AsyncServer

解决 Flask-SocketIO 与 ASGI 不兼容的问题
使用原生 python-socketio 的 AsyncServer 以获得完整的 ASGI 支持
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 导入 Flask 应用（不包含 SocketIO）
from flask import Flask
from flask_cors import CORS

# 创建 Flask 应用（从 server.app 中提取，但不包含 SocketIO）
# 注意：我们需要重新创建 app，因为原来的 app 绑定了 Flask-SocketIO
app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], 
                                  "headers": ["Content-Type", "Authorization", "X-Requested-With"]}})

# 导入所有 Flask 路由（但不包括 SocketIO 事件）
# 我们需要手动导入路由，或者使用一个包装器
# #region agent log
import json
import datetime
_log_file = Path(__file__).parent.parent / '.cursor' / 'debug.log'
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:29','message':'Before route import','data':{}})+'\n')
except: pass
# #endregion
try:
    # 方法：延迟导入，避免 Flask-SocketIO 初始化
    # 先导入 Flask 和装饰器，然后手动注册路由
    import importlib
    import types
    
    # 导入 server.app 模块，但避免执行 SocketIO 相关代码
    # 关键：临时设置 USE_GRANIAN=false，避免 Flask-SocketIO 尝试使用 ASGI 模式
    original_use_granian = os.environ.get('USE_GRANIAN')
    os.environ['USE_GRANIAN'] = 'false'  # 临时禁用，避免 Flask-SocketIO 初始化错误
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:38','message':'Before import_module','data':{'temp_use_granian':'false'}})+'\n')
    except: pass
    # #endregion
    try:
        app_module = importlib.import_module('server.app')
    finally:
        # 恢复原始环境变量
        if original_use_granian is not None:
            os.environ['USE_GRANIAN'] = original_use_granian
        elif 'USE_GRANIAN' in os.environ:
            del os.environ['USE_GRANIAN']
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:41','message':'After import_module','data':{'has_app':hasattr(app_module,'app')}})+'\n')
    except: pass
    # #endregion
    original_app = app_module.app
    
    # 复制所有路由到新的 app
    copied_count = 0
    for rule in original_app.url_map.iter_rules():
        endpoint = rule.endpoint
        # 跳过 static 和 socketio 相关端点
        if endpoint == 'static' or 'socketio' in endpoint.lower():
            continue
        
        try:
            # 获取视图函数
            view_func = original_app.view_functions.get(endpoint)
            if view_func is None:
                continue
            
            # 注册到新 app
            app.add_url_rule(
                rule.rule,
                endpoint=endpoint,
                view_func=view_func,
                methods=rule.methods
            )
            copied_count += 1
        except Exception as e:
            # 某些路由可能无法复制，跳过
            pass
    
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:65','message':'Route copy success','data':{'copied_count':copied_count}})+'\n')
    except: pass
    # #endregion
    print(f"[OK] 已复制 {copied_count} 个路由到 ASGI 应用")
except Exception as e:
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:70','message':'Route import failed','data':{'error':str(e),'type':type(e).__name__}})+'\n')
    except: pass
    # #endregion
    print(f"[WARNING] 导入路由失败: {e}")
    import traceback
    traceback.print_exc()

# 创建异步 SocketIO 服务器（关键：使用 AsyncServer）
# #region agent log
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:72','message':'Before socketio import','data':{}})+'\n')
except: pass
# #endregion
try:
    import socketio
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:75','message':'SocketIO import success','data':{}})+'\n')
    except: pass
    # #endregion
    # 使用 AsyncServer（支持 ASGI）
    sio = socketio.AsyncServer(
        async_mode='asgi',
        cors_allowed_origins='*',
        logger=False,
        engineio_logger=False,
        ping_interval=25000,
        ping_timeout=60000
    )
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:85','message':'AsyncServer created','data':{}})+'\n')
    except: pass
    # #endregion
except ImportError as e:
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:88','message':'SocketIO import failed','data':{'error':str(e)}})+'\n')
    except: pass
    # #endregion
    raise ImportError("python-socketio[asyncio] is required: pip install 'python-socketio[asyncio]'")

# 导入 SocketIO 事件处理器（需要转换为异步）
# 注意：需要将同步事件处理器转换为异步版本
from server.asgi_socketio_handlers import register_handlers
register_handlers(sio)

# 关键：使用 ASGIApp 包装
# Granian 收到请求 -> 如果是 /socket.io/ 开头 -> 交给 sio 处理
#                  -> 如果是其他 HTTP 请求 -> 自动转给 Flask (app) 处理
# 重要：Flask 应用需要包装成 ASGI 应用
try:
    from asgiref.wsgi import WsgiToAsgi
    flask_asgi_app = WsgiToAsgi(app)
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:160','message':'Flask wrapped to ASGI','data':{}})+'\n')
    except: pass
    # #endregion
except ImportError:
    # 如果 asgiref 不可用，尝试直接使用（可能会失败）
    flask_asgi_app = app
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:167','message':'asgiref not available, using Flask directly','data':{}})+'\n')
    except: pass
    # #endregion

# #region agent log
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:170','message':'Before ASGIApp creation','data':{}})+'\n')
except: pass
# #endregion
app_asgi = socketio.ASGIApp(sio, other_asgi_app=flask_asgi_app, socketio_path='socket.io')
# #region agent log
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'sessionId':'debug-session','runId':'run1','hypothesisId':'B','timestamp':int(datetime.datetime.now().timestamp()*1000),'location':'asgi_entry.py:97','message':'ASGIApp created','data':{'type':str(type(app_asgi))}})+'\n')
except: pass
# #endregion

# 导出给 Granian 使用
asgi_app = app_asgi

