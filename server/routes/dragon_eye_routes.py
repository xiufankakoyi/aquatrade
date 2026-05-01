"""
DragonEye 路由模块
提供爬虫、数据清洗、飞书推送的 API 端点
支持 SSE 实时日志流
"""
import json
import time
import queue
import threading
import polars as pl
from flask import Blueprint, request, jsonify, Response, stream_with_context
from datetime import datetime
from config.logger import get_logger
from core.dragon_eye.service import DragonEyeService
from core.dragon_eye.job_manager import job_manager

logger = get_logger(__name__)
dragon_bp = Blueprint('dragon', __name__, url_prefix='/api/dragon')
service = DragonEyeService()


# ==========================================
# 爬虫任务相关接口
# ==========================================

@dragon_bp.route('/crawl', methods=['POST'])
def trigger_crawl():
    """
    启动爬虫任务
    
    Request Body:
        - date: 目标日期 (YYYY-MM-DD)，默认为今天
        - sync: 是否同步等待结果，默认 False
        
    Returns:
        - job_id: 任务ID
        - status: 任务状态
        - message: 提示信息
    """
    data = request.json or {}
    target_date = data.get('date') or datetime.now().strftime("%Y-%m-%d")
    sync = data.get('sync', False)
    
    try:
        job_id = service.run_crawler(target_date)
        
        if sync:
            # 同步模式：等待任务完成
            max_wait = 300  # 最多等待5分钟
            waited = 0
            while waited < max_wait:
                job = job_manager.get_job(job_id)
                if job and job.status in ['completed', 'failed']:
                    break
                time.sleep(1)
                waited += 1
            
            job = job_manager.get_job(job_id)
            return jsonify({
                "job_id": job_id,
                "status": job.status if job else "unknown",
                "progress": job.progress if job else 0,
                "message": job.message if job else ""
            })
        
        # 异步模式：立即返回任务ID
        return jsonify({
            "job_id": job_id,
            "status": "running",
            "message": f"爬虫任务已启动，目标日期: {target_date}"
        })
        
    except Exception as e:
        logger.error(f"Failed to start crawl: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/clean', methods=['POST'])
def trigger_clean():
    """
    启动数据清洗任务
    
    Request Body:
        - date: 目标日期 (YYYY-MM-DD)
        
    Returns:
        - job_id: 任务ID
        - status: 任务状态
    """
    data = request.json or {}
    target_date = data.get('date')
    
    if not target_date:
        return jsonify({"error": "Missing date parameter"}), 400
    
    try:
        job_id = service.process_and_persist(target_date)
        return jsonify({
            "job_id": job_id,
            "status": "running",
            "message": f"清洗任务已启动，目标日期: {target_date}"
        })
    except Exception as e:
        logger.error(f"Failed to start clean: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/pipeline', methods=['POST'])
def trigger_pipeline():
    """
    启动完整工作流：爬虫 -> 清洗 -> 推送
    
    Request Body:
        - date: 目标日期 (YYYY-MM-DD)
        - push_feishu: 是否推送到飞书，默认 True
        
    Returns:
        - job_id: 任务ID
        - status: 任务状态
    """
    data = request.json or {}
    target_date = data.get('date') or datetime.now().strftime("%Y-%m-%d")
    push_feishu = data.get('push_feishu', True)
    
    try:
        job_id = service.run_full_pipeline(target_date, push_feishu)
        return jsonify({
            "job_id": job_id,
            "status": "running",
            "message": f"完整工作流已启动，目标日期: {target_date}"
        })
    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}")
        return jsonify({"error": str(e)}), 500


# ==========================================
# 任务状态查询接口
# ==========================================

@dragon_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """
    获取任务状态
    
    Path Parameters:
        - job_id: 任务ID
        
    Returns:
        - 完整的任务状态信息
    """
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify(job.to_dict())


@dragon_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """
    获取最近的任务列表
    
    Query Parameters:
        - type: 任务类型过滤 (crawl, clean, push, full_pipeline)
        - limit: 返回数量限制，默认 10
        
    Returns:
        - jobs: 任务列表
    """
    job_type = request.args.get('type')
    limit = int(request.args.get('limit', 10))
    
    jobs = job_manager.get_recent_jobs(job_type, limit)
    return jsonify({
        "jobs": [job.to_dict() for job in jobs],
        "total": len(jobs)
    })


# ==========================================
# SSE 实时日志流接口
# ==========================================

@dragon_bp.route('/stream/<job_id>')
def stream_logs(job_id):
    """
    SSE 实时日志流
    
    Path Parameters:
        - job_id: 任务ID
        
    Returns:
        - text/event-stream: 实时日志流
    """
    def generate():
        # 发送初始连接确认
        yield f"data: {json.dumps({'type': 'connected', 'job_id': job_id})}\n\n"
        
        # 获取任务信息
        job = job_manager.get_job(job_id)
        if not job:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return
        
        # 发送历史日志
        for log in job.logs:
            yield f"data: {json.dumps({'type': 'log', 'data': log})}\n\n"
        
        # 如果任务已完成，发送完成标记
        if job.status in ['completed', 'failed']:
            yield f"data: {json.dumps({'type': 'complete', 'status': job.status})}\n\n"
            return
        
        # 创建队列接收实时日志
        log_queue = queue.Queue()
        
        def on_log(log_entry):
            log_queue.put(log_entry)
        
        # 订阅日志更新
        service.subscribe_job_logs(job_id, on_log)
        
        # 持续发送新日志
        last_heartbeat = time.time()
        while True:
            try:
                # 非阻塞获取日志，超时 1 秒
                log_entry = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'type': 'log', 'data': log_entry})}\n\n"
            except queue.Empty:
                # 发送心跳保持连接
                if time.time() - last_heartbeat > 15:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    last_heartbeat = time.time()
                
                # 检查任务状态
                job = job_manager.get_job(job_id)
                if job and job.status in ['completed', 'failed']:
                    # 发送最终状态
                    yield f"data: {json.dumps({'type': 'complete', 'status': job.status, 'progress': job.progress})}\n\n"
                    break
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# ==========================================
# 数据查询接口
# ==========================================

@dragon_bp.route('/stocks', methods=['GET'])
def get_dragon_stocks():
    """
    获取指定时间段的龙头股数据
    
    Query Parameters:
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        
    Returns:
        - stocks: 龙头股列表
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    
    try:
        df = service.manager.get_historical_dragon(start_date, end_date)
        
        # 处理日期格式
        if not df.is_empty() and 'trade_date' in df.columns:
            # 检查日期列类型，如果是字符串则不需要转换
            if df['trade_date'].dtype == pl.Date:
                df = df.with_columns(
                    pl.col('trade_date').dt.strftime('%Y-%m-%d').alias('trade_date')
                )
            elif df['trade_date'].dtype == pl.Datetime:
                df = df.with_columns(
                    pl.col('trade_date').dt.strftime('%Y-%m-%d').alias('trade_date')
                )
            # 如果是字符串类型，保持不变
        
        return jsonify(df.to_dicts())
    except Exception as e:
        logger.error(f"Failed to get stocks: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/sentiment', methods=['GET'])
def get_market_sentiment():
    """
    获取指定时间段的市场情绪数据
    
    Query Parameters:
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        
    Returns:
        - sentiment: 市场情绪数据列表
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    
    try:
        df = service.manager.get_market_sentiment(start_date, end_date)
        return jsonify(df.to_dicts())
    except Exception as e:
        logger.error(f"Failed to get sentiment: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/brief', methods=['GET'])
def get_ai_brief():
    """
    获取指定日期的 AI 简报
    
    Query Parameters:
        - date: 日期 (YYYY-MM-DD)
        
    Returns:
        - date: 日期
        - content: 简报内容
    """
    date = request.args.get('date')
    if not date:
        return jsonify({"error": "Missing date parameter"}), 400
    
    brief = service.get_latest_brief(date)
    return jsonify({
        "date": date,
        "content": brief,
        "has_data": bool(brief)
    })


# ==========================================
# 飞书推送接口
# ==========================================

@dragon_bp.route('/push', methods=['POST'])
def push_to_feishu():
    """
    推送到飞书
    
    Request Body:
        - date: 日期 (YYYY-MM-DD)
        
    Returns:
        - status: 推送状态
        - message: 提示信息
    """
    data = request.json or {}
    date = data.get('date')
    
    if not date:
        return jsonify({"error": "Missing date parameter"}), 400
    
    try:
        success, msg = service.send_to_feishu(date)
        if not success:
            return jsonify({"error": msg}), 500
        
        return jsonify({
            "status": "success",
            "message": msg
        })
    except Exception as e:
        logger.error(f"Failed to push to feishu: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/confirm', methods=['POST'])
def confirm_and_push():
    """
    确认数据并推送到飞书（兼容旧接口）
    
    Request Body:
        - date: 日期 (YYYY-MM-DD)
        
    Returns:
        - status: 推送状态
        - message: 提示信息
    """
    return push_to_feishu()


# ==========================================
# 数据可视化分析接口
# ==========================================

@dragon_bp.route('/limit-up-trend', methods=['GET'])
def get_limit_up_trend():
    """
    获取涨停趋势数据
    
    Query Parameters:
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        
    Returns:
        - dates: 日期列表
        - limit_up_counts: 涨停数量列表
        - max_heights: 最高连板数列表
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    
    try:
        df = service.manager.get_market_sentiment(start_date, end_date)
        
        if df.is_empty():
            return jsonify({"dates": [], "limit_up_counts": [], "max_heights": []})
        
        # 按日期排序
        df = df.sort('trade_date')
        
        # 转换日期为字符串格式
        dates = df['trade_date'].dt.strftime('%Y-%m-%d').to_list() if 'trade_date' in df.columns else []
        
        result = {
            "dates": dates,
            "limit_up_counts": df['limit_up_count'].to_list() if 'limit_up_count' in df.columns else [],
            "max_heights": df['max_height'].to_list() if 'max_height' in df.columns else [],
            "broken_ratios": df['broken_ratio'].to_list() if 'broken_ratio' in df.columns else [],
            "limit_down_counts": df['limit_down_count'].to_list() if 'limit_down_count' in df.columns else []
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get limit up trend: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/bubble-matrix', methods=['GET'])
def get_bubble_matrix():
    """
    获取涨停强度气泡图数据
    
    Query Parameters:
        - date: 日期 (YYYY-MM-DD)
        
    Returns:
        - bubbles: 气泡数据列表
            - stock_code: 股票代码
            - stock_name: 股票名称
            - continue_num: 连板数
            - market_cap: 市值（亿元）
            - limit_up_time: 封板时间（分钟数，如 9:30 = 570）
            - order_amount: 封单额
            - turnover_rate: 换手率
            - quadrant: 象限 (1-4)
            - theme: 题材
    """
    target_date = request.args.get('date')
    
    if not target_date:
        return jsonify({"error": "Missing date parameter"}), 400
    
    try:
        # 从原始数据文件读取更完整的信息
        bubbles = service.get_bubble_matrix_data(target_date)
        return jsonify(bubbles)
    except Exception as e:
        logger.error(f"Failed to get bubble matrix: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/theme-flow', methods=['GET'])
def get_theme_flow():
    """
    获取题材流向数据
    
    Query Parameters:
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        
    Returns:
        - nodes: 节点列表 [{name, date, count, is_main}]
        - links: 连接列表 [{source, target, value}]
    """
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
    
    try:
        flow_data = service.get_theme_flow_data(start_date, end_date)
        return jsonify(flow_data)
    except Exception as e:
        logger.error(f"Failed to get theme flow: {e}")
        return jsonify({"error": str(e)}), 500


@dragon_bp.route('/latest-date', methods=['GET'])
def get_latest_date():
    """
    获取数据库中最新的数据日期
    
    Returns:
        - latest_date: 最新日期 (YYYY-MM-DD)
        - has_data: 是否有数据
    """
    try:
        # 获取最近 30 天的数据，找到最新的日期
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=30)
        
        df = service.manager.get_market_sentiment(
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d')
        )
        
        if df.is_empty():
            return jsonify({
                "latest_date": None,
                "has_data": False
            })
        
        # 获取最新日期
        latest_date = df['trade_date'].max()
        if hasattr(latest_date, 'strftime'):
            latest_date = latest_date.strftime('%Y-%m-%d')
        else:
            latest_date = str(latest_date)
        
        return jsonify({
            "latest_date": latest_date,
            "has_data": True
        })
    except Exception as e:
        logger.error(f"Failed to get latest date: {e}")
        return jsonify({"error": str(e)}), 500
