"""
系统相关路由
"""
import json
import time
from flask import Blueprint, jsonify, Response, stream_with_context
from server.utils.system import _schedule_restart

system_bp = Blueprint('system', __name__, url_prefix='/api')


@system_bp.route('/', methods=['GET'])
def index():
    """根路径路由"""
    response = jsonify({"success": True, "message": "服务器正在运行"})
    response.headers.add('Content-Type', 'application/json')
    return response


@system_bp.route('/direct_test', methods=['GET'])
def direct_test():
    """全新的、完全独立的测试端点，用于调试路由和响应处理"""
    test_data = {"success": True, "data": [{"id": "test1", "name": "测试数据1"}]}
    return jsonify(test_data)


@system_bp.route('/restart-backend', methods=['POST'])
def restart_backend():
    """
    触发后端自我重启：立即给前端成功响应，再在后台调用 os.execl 重新拉起进程。
    """
    _schedule_restart()
    return jsonify({"success": True, "message": "后端正在重启，请稍候 1-2 秒"}), 202


@system_bp.route('/startup-status', methods=['GET'])
def get_startup_status():
    """
    获取启动状态
    返回三阶段自检的当前进度
    """
    from server.services.startup_service import get_startup_service
    
    service = get_startup_service()
    return jsonify(service.get_status())


@system_bp.route('/startup-logs', methods=['GET'])
def stream_startup_logs():
    """
    SSE 流式推送启动日志
    前端通过 EventSource 连接，实时接收日志更新
    """
    from server.services.startup_service import get_startup_service
    
    service = get_startup_service()
    
    def generate():
        last_log_count = 0
        last_status = None
        max_iterations = 300
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            status = service.get_status()
            
            if status != last_status:
                last_status = status
                yield f"data: {json.dumps(status)}\n\n"
            
            if status.get('ready') or status.get('error_code'):
                break
            
            time.sleep(0.1)
        
        yield f"data: {json.dumps({'event': 'close'})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@system_bp.route('/startup-begin', methods=['POST'])
def begin_startup():
    """
    触发启动检查
    前端加载完成后调用此接口开始后台自检
    """
    from server.services.startup_service import get_startup_service
    
    service = get_startup_service()
    
    if service.is_ready():
        return jsonify({"success": True, "message": "系统已就绪", "status": service.get_status()})
    
    if service.has_error():
        return jsonify({"success": False, "message": "启动检查失败", "status": service.get_status()})
    
    service.start_async()
    
    return jsonify({"success": True, "message": "启动检查已开始", "status": service.get_status()})
