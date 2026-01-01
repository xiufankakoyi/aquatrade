import os
import sys
import time
from pathlib import Path
import socketio
from asgiref.wsgi import WsgiToAsgi

# #region agent log
_start_time = time.perf_counter()
_log_file = r'd:\aquatrade\.cursor\debug.log'
import json
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:start","message":"run.py 开始执行","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
except: pass
# #endregion

# 1. 路径设置
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# #region agent log
_t1 = time.perf_counter()
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:before_import","message":"准备导入 server.app","data":{"elapsed":_t1-_start_time},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
except: pass
# #endregion

# 2. 导入 Flask app 和 socketio 实例
# 请确保 server/app.py 里的 socketio 变量名一致
from server.app import app, socketio as flask_sio

# #region agent log
_t2 = time.perf_counter()
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:after_import","message":"server.app 导入完成","data":{"elapsed":_t2-_t1,"total":_t2-_start_time},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"A"}) + "\n")
except: pass
# #endregion

# 3. 转换 Flask 路由为 ASGI (WSGI 转 ASGI)
# 这一层负责处理所有正常的 API 和 HTML 页面
flask_wsgi_app_base = WsgiToAsgi(app)

# 3.1. 创建 lifespan 处理器：在 WsgiToAsgi 之前拦截 lifespan scope
async def lifespan_handler(scope, receive, send):
    """处理 lifespan scope，只有 HTTP 请求才传递给 Flask WSGI"""
    if scope['type'] == 'lifespan':
        # #region agent log
        try:
            with open(_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:lifespan_handler","message":"处理 lifespan scope","data":{},"sessionId":"debug-session","runId":"lifespan-debug","hypothesisId":"F"}) + "\n")
        except: pass
        # #endregion
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await send({'type': 'lifespan.shutdown.complete'})
                return
    else:
        # 只有非 lifespan 请求才传给 Flask WSGI
        await flask_wsgi_app_base(scope, receive, send)

flask_wsgi_app = lifespan_handler

# #region agent log
_t3 = time.perf_counter()
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:after_wsgi","message":"Flask 包装为 ASGI 完成","data":{"elapsed":_t3-_t2,"total":_t3-_start_time},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"D"}) + "\n")
except: pass
# #endregion

# 4. 获取或创建 SocketIO 服务器
# 在 ASGI 模式下，需要创建 AsyncServer 而不是使用 Flask-SocketIO 的 threading 服务器
# 注意：当使用 Granian ASGI 服务器时，必须使用 AsyncServer
# 检查是否通过 Granian 启动（通过检查命令行参数或环境变量）
use_asgi = os.getenv("USE_GRANIAN", "false").lower() == "true"
# 如果通过 Granian 启动（ASGI 接口），强制使用 AsyncServer
# Granian 使用 --interface asgi，所以我们必须使用 AsyncServer
if not use_asgi:
    # 检查是否在 ASGI 环境中（通过检查 sys.argv 或其他方式）
    # 如果通过 granian --interface asgi 启动，强制使用 AsyncServer
    use_asgi = True  # 强制使用，因为 run.py 是通过 Granian ASGI 调用的

if use_asgi:
    # ASGI 模式：创建新的 AsyncServer（兼容 ASGI）
    # 然后注册事件处理器（从 asgi_socketio_handlers 导入）
    try:
        sio_server = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',  # 字符串格式
            cors_credentials=True,
            logger=False,
            engineio_logger=False,
            ping_interval=25000,
            ping_timeout=60000
        )
        # 注册事件处理器（关键：这样才能处理 run_streaming_backtest 等事件）
        from server.asgi_socketio_handlers import register_handlers
        try:
            register_handlers(sio_server)
            # #region agent log
            try:
                with open(_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:register_handlers","message":"事件处理器注册成功","data":{},"sessionId":"debug-session","runId":"cors-debug","hypothesisId":"D"}) + "\n")
            except: pass
            # #endregion
        except Exception as e:
            # #region agent log
            try:
                with open(_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:register_handlers","message":"事件处理器注册失败","data":{"error":str(e),"type":type(e).__name__},"sessionId":"debug-session","runId":"cors-debug","hypothesisId":"D"}) + "\n")
            except: pass
            # #endregion
            raise
    except Exception as e:
        # 如果 AsyncServer 创建失败，回退到使用 flask_sio.server
        # 但需要确保它能正常工作
        import warnings
        warnings.warn(f"Failed to create AsyncServer: {e}, falling back to flask_sio.server")
        sio_server = flask_sio.server
else:
    # WSGI 模式：使用 Flask-SocketIO 的服务器
    sio_server = flask_sio.server

# #region agent log
_t4 = time.perf_counter()
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:after_sio","message":"SocketIO 服务器获取完成","data":{"elapsed":_t4-_t3,"total":_t4-_start_time,"use_asgi":use_asgi,"server_type":type(sio_server).__name__},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"B"}) + "\n")
except: pass
# #endregion

# 5. 最终组合 (ASGI 分发器)
# - 如果路径是 /socket.io -> 由 sio_server 直接处理 (不走 Flask，不卡顿)
# - 其他路径 -> 由 flask_wsgi_app 处理 (正常的 API)
base_app_asgi = socketio.ASGIApp(
    socketio_server=sio_server,
    other_asgi_app=flask_wsgi_app,
    socketio_path='socket.io'
)

# 包装 ASGI 应用以捕获所有异常并记录日志
async def error_handler_wrapper(scope, receive, send):
    """ASGI 包装器：捕获所有异常并记录详细日志，强制打印到 stderr"""
    import sys
    import traceback
    
    
    try:
        # #region agent log
        if scope["type"] == "http":
            try:
                with open(_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:error_handler","message":"HTTP 请求到达","data":{"method":scope.get("method","N/A"),"path":scope.get("path","N/A"),"query_string":scope.get("query_string",b"").decode()},"sessionId":"debug-session","runId":"error-debug","hypothesisId":"E"}) + "\n")
            except: pass
        # #endregion
        await base_app_asgi(scope, receive, send)
    except Exception as e:
        # 强制打印异常到 stderr
        print(f"[ERROR] ASGI application exception:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        print(f"[ERROR] Exception type: {type(e).__name__}", file=sys.stderr, flush=True)
        print(f"[ERROR] Exception message: {str(e)}", file=sys.stderr, flush=True)
        
        # #region agent log
        try:
            tb_str = traceback.format_exc()
            with open(_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:error_handler","message":"ASGI 应用异常","data":{"error":str(e),"type":type(e).__name__,"traceback":tb_str,"scope_type":scope.get("type","N/A")},"sessionId":"debug-session","runId":"error-debug","hypothesisId":"E"}) + "\n")
        except: pass
        # #endregion
        
        # 如果还没有发送响应，发送错误响应
        if scope["type"] == "http":
            try:
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"text/plain; charset=utf-8"),
                        (b"access-control-allow-origin", b"*"),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": f"Internal Server Error: {str(e)}".encode('utf-8')
                })
            except Exception as send_error:
                print(f"[ERROR] Failed to send error response: {send_error}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
        raise

# 6. CORS 中间件：确保所有响应包含 CORS 头
async def cors_middleware_wrapper(scope, receive, send):
    """ASGI 中间件：为所有响应添加 CORS 头"""
    # 对于非 HTTP 请求（如 lifespan, websocket），直接传递给底层应用
    if scope["type"] != "http":
        await base_app_asgi(scope, receive, send)
        return
    
    # #region agent log
    try:
        with open(_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:cors_middleware","message":"CORS 中间件被调用","data":{"type":scope["type"],"method":scope.get("method","N/A"),"path":scope.get("path","N/A")},"sessionId":"debug-session","runId":"cors-debug","hypothesisId":"C"}) + "\n")
    except: pass
    # #endregion
    
    # 如果是 OPTIONS 请求（预检请求），直接返回
    if scope["method"] == "OPTIONS":
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-methods", b"GET, POST, OPTIONS, PUT, DELETE"),
                (b"access-control-allow-headers", b"Content-Type, Authorization, X-Requested-With"),
                (b"access-control-allow-credentials", b"true"),
                (b"content-length", b"0"),
            ],
        })
        await send({"type": "http.response.body", "body": b""})
        return
    
    # 对于其他请求，包装 send 函数以添加 CORS 头
    response_started = False
    
    async def send_wrapper(message):
        nonlocal response_started
        if message["type"] == "http.response.start":
            response_started = True
            # 获取现有头部
            headers = list(message.get("headers", []))
            # 添加 CORS 头（如果不存在）
            header_dict = {k.lower(): v for k, v in headers}
            if b"access-control-allow-origin" not in header_dict:
                headers.append((b"access-control-allow-origin", b"*"))
            if b"access-control-allow-methods" not in header_dict:
                headers.append((b"access-control-allow-methods", b"GET, POST, OPTIONS, PUT, DELETE"))
            if b"access-control-allow-headers" not in header_dict:
                headers.append((b"access-control-allow-headers", b"Content-Type, Authorization, X-Requested-With"))
            if b"access-control-allow-credentials" not in header_dict:
                headers.append((b"access-control-allow-credentials", b"true"))
            message["headers"] = headers
        await send(message)
    
    try:
        # 调用原始应用，使用包装后的 send
        await base_app_asgi(scope, receive, send_wrapper)
    except Exception as e:
        # #region agent log
        try:
            with open(_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:cors_middleware","message":"CORS 中间件异常","data":{"error":str(e),"type":type(e).__name__},"sessionId":"debug-session","runId":"cors-debug","hypothesisId":"C"}) + "\n")
        except: pass
        # #endregion
        # 如果应用出错，确保发送错误响应时也包含 CORS 头
        if not response_started:
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-methods", b"GET, POST, OPTIONS, PUT, DELETE"),
                    (b"access-control-allow-headers", b"Content-Type, Authorization, X-Requested-With"),
                    (b"access-control-allow-credentials", b"true"),
                    (b"content-type", b"text/plain"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": f"Internal Server Error: {str(e)}".encode()
            })
        raise

# 使用错误处理包装器
app_asgi = error_handler_wrapper

# #region agent log
_t5 = time.perf_counter()
try:
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"run.py:after_asgi","message":"ASGI 应用创建完成","data":{"elapsed":_t5-_t4,"total":_t5-_start_time},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"D"}) + "\n")
except: pass
# #endregion

if __name__ == "__main__":
    print("🚀 系统正在以 ASGI 独立分发模式启动...")