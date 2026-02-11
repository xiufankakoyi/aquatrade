# server/routes/dragon_eye_routes.py
from flask import Blueprint, request, jsonify
from core.dragon_eye.service import DragonEyeService
from datetime import datetime
import threading
from config.logger import get_logger

logger = get_logger(__name__)
dragon_bp = Blueprint('dragon', __name__, url_prefix='/api/dragon')
service = DragonEyeService()

@dragon_bp.route('/crawl', methods=['POST'])
def trigger_crawl():
    """异步触发龙大爬虫抓取数据"""
    data = request.json or {}
    target_date = data.get('date') or datetime.now().strftime("%Y-%m-%d")
    
    def run_and_process():
        logger.info(f"Background task started for date: {target_date}")
        success, msg = service.run_crawler(target_date)
        if success:
            service.process_and_persist(target_date)
            logger.info(f"Background task finished for date: {target_date}")
        else:
            logger.error(f"Background task failed: {msg}")

    thread = threading.Thread(target=run_and_process)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "date": target_date})

@dragon_bp.route('/stocks', methods=['GET'])
def get_dragon_stocks():
    """获取指定时间段的龙头股数据"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
        
    try:
        df = service.manager.get_historical_dragon(start_date, end_date)
        return jsonify(df.to_dicts())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dragon_bp.route('/sentiment', methods=['GET'])
def get_market_sentiment():
    """获取指定时间段的市场情绪数据"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400
        
    try:
        df = service.manager.get_market_sentiment(start_date, end_date)
        return jsonify(df.to_dicts())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dragon_bp.route('/brief', methods=['GET'])
def get_ai_brief():
    """获取指定日期的 AI 简报"""
    date = request.args.get('date')
    if not date:
        return jsonify({"error": "Missing date"}), 400
    brief = service.get_latest_brief(date)
    return jsonify({"date": date, "content": brief})

@dragon_bp.route('/confirm', methods=['POST'])
def confirm_and_push():
    """确认数据并推送到飞书"""
    data = request.json or {}
    date = data.get('date')
    if not date:
        return jsonify({"error": "Missing date"}), 400
        
    success, msg = service.send_to_feishu(date)
    if not success:
        return jsonify({"error": msg}), 500
    return jsonify({"status": "pushed", "message": msg})
