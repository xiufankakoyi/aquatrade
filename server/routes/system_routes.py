"""
系统相关路由
"""
from flask import Blueprint, jsonify
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
    # 这个端点不使用任何外部依赖，直接返回硬编码数据
    test_data = {"success": True, "data": [{"id": "test1", "name": "测试数据1"}]}
    return jsonify(test_data)


@system_bp.route('/restart-backend', methods=['POST'])
def restart_backend():
    """
    触发后端自我重启：立即给前端成功响应，再在后台调用 os.execl 重新拉起进程。
    """
    _schedule_restart()
    return jsonify({"success": True, "message": "后端正在重启，请稍候 1-2 秒"}), 202

