"""
优化相关路由
"""
from flask import Blueprint, request, jsonify
import uuid
import threading
from config.logger import get_logger

optimization_bp = Blueprint('optimization', __name__, url_prefix='/api')
logger = get_logger(__name__)


@optimization_bp.route("/ga_optimize/start", methods=["POST"])
def api_ga_start():
    """
    开始GA优化任务
    返回task_id供前端轮询
    """
    # 延迟导入避免循环依赖
    from server.logic.optimization import ga_tasks, ga_worker
    
    data = request.get_json(force=True) or {}
    
    # 获取必要参数
    strategy_id = data.get("strategy_id", "聚宽量比市值策略V3_严格趋势")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    pop_size = int(data.get("pop_size", 20))
    generations = int(data.get("generations", 20))
    
    # 参数验证
    if not start_date or not end_date:
        return jsonify({"error": "start_date / end_date 必填"}), 400
    
    # 生成任务ID并初始化任务
    task_id = str(uuid.uuid4())
    ga_tasks[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
    }
    
    # 构建GA优化参数
    args = dict(
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        pop_size=pop_size,
        generations=generations,
        db_path=None,
        keys=None  # 使用全部参数进行优化
    )
    
    # 启动后台线程执行GA优化
    t = threading.Thread(target=ga_worker, args=(task_id, args), daemon=True)
    t.start()
    
    logger.info(f"启动GA优化任务 (task_id: {task_id}, strategy: {strategy_id})")
    
    # 返回任务ID给前端
    return jsonify({"ok": True, "task_id": task_id})


@optimization_bp.route("/ga_optimize/status/<task_id>", methods=["GET"])
def api_ga_status(task_id: str):
    """
    查询GA优化任务状态
    """
    # 延迟导入避免循环依赖
    from server.logic.optimization import ga_tasks
    
    # 查找任务
    task = ga_tasks.get(task_id)
    if not task:
        return jsonify({"error": "unknown task_id"}), 404
    
    # 返回任务状态
    return jsonify(task)

