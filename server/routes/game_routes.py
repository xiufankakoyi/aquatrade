"""
K线盘感训练游戏路由

API接口：
- POST /api/game/start: 开始新游戏
- POST /api/game/next: 显示下一根K线
- POST /api/game/buy: 买入
- POST /api/game/sell: 卖出
- GET /api/game/result: 获取游戏结果
- POST /api/game/reset: 重置游戏
- GET /api/game/state: 获取游戏状态
"""

from flask import Blueprint, request
from server.performance_utils import json_response
from server.services.game_service import get_game_service
from config.logger import get_logger

logger = get_logger(__name__)

game_bp = Blueprint('game', __name__, url_prefix='/api/game')

VALID_POSITION_RATIOS = [0.25, 0.5, 1.0]


@game_bp.route('/start', methods=['POST'])
def start_game():
    """
    开始新游戏
    
    Request Body:
        {
            "initial_capital": 10000.0,  # 初始资金（可选，默认10000）
            "volatility_filter": "random"  # 波动率筛选模式: random/high/extreme
        }
    
    Response:
        {
            "success": true,
            "data": {
                "session_id": "abc123",
                "stock_code": "000001.SZ",
                "stock_name": "平安银行",
                "initial_capital": 10000.0,
                "history_klines": [...],  # 历史窗口K线（60根）
                "current_kline": {...},   # 当前交易K线
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        initial_capital = float(data.get('initial_capital', 10000.0))
        volatility_filter = data.get('volatility_filter', 'random')
        
        if initial_capital <= 0:
            return json_response({
                "success": False,
                "error": "初始资金必须大于0"
            }, status_code=400)
        
        if volatility_filter not in ['random', 'high', 'extreme']:
            volatility_filter = 'random'
        
        game_service = get_game_service()
        result = game_service.start_new_game(initial_capital, volatility_filter)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 开始游戏失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/next', methods=['POST'])
def next_kline():
    """
    显示下一根K线
    
    Request Body:
        {
            "session_id": "abc123"
        }
    
    Response:
        {
            "success": true,
            "data": {
                "current_kline": {...},
                "is_finished": false,
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        game_service = get_game_service()
        result = game_service.next_kline(session_id)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 下一根K线失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/fast_forward', methods=['POST'])
def fast_forward():
    """
    快进功能：一次跳过多根K线
    
    Request Body:
        {
            "session_id": "abc123",
            "steps": 5  # 跳过的K线数量 (1-20)
        }
    
    Response:
        {
            "success": true,
            "data": {
                "skipped_klines": [...],  # 被跳过的K线列表
                "current_kline": {...},   # 当前K线
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        steps = int(data.get('steps', 5))
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        # 限制步数范围
        steps = max(1, min(20, steps))
        
        game_service = get_game_service()
        result = game_service.fast_forward(session_id, steps)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 快进失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/buy', methods=['POST'])
def buy():
    """
    买入操作
    
    Request Body:
        {
            "session_id": "abc123",
            "position_ratio": 0.25  # 仓位比例：0.25（1/4仓）、0.5（半仓）、1.0（全仓）
        }
    
    Response:
        {
            "success": true,
            "data": {
                "trade": {...},
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        position_ratio = float(data.get('position_ratio', 0.25))
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        if position_ratio not in VALID_POSITION_RATIOS:
            position_ratio = 0.25
        
        game_service = get_game_service()
        result = game_service.buy(session_id, position_ratio)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 买入失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/sell', methods=['POST'])
def sell():
    """
    卖出操作
    
    Request Body:
        {
            "session_id": "abc123",
            "position_ratio": 0.25  # 仓位比例：0.25（1/4仓）、0.5（半仓）、1.0（全仓）
        }
    
    Response:
        {
            "success": true,
            "data": {
                "trade": {...},
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        position_ratio = float(data.get('position_ratio', 0.25))
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        if position_ratio not in VALID_POSITION_RATIOS:
            position_ratio = 0.25
        
        game_service = get_game_service()
        result = game_service.sell(session_id, position_ratio)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 卖出失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/result', methods=['GET'])
def get_result():
    """
    获取游戏结果
    
    Query Params:
        session_id: 会话ID
    
    Response:
        {
            "success": true,
            "data": {
                "stock_code": "...",
                "stock_name": "...",
                "initial_capital": 10000.0,
                "final_assets": 12000.0,
                "statistics": {...},
                "trades": [...],
                "trade_markers": [...],
                "all_klines": [...],
                "asset_history": [...],
                "history_klines_count": 60
            }
        }
    """
    try:
        session_id = request.args.get('session_id')
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        game_service = get_game_service()
        result = game_service.get_game_result(session_id)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 获取结果失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/reset', methods=['POST'])
def reset_game():
    """
    重置游戏（开始新局）
    
    Request Body:
        {
            "session_id": "abc123",
            "initial_capital": 10000.0  # 可选
        }
    
    Response:
        {
            "success": true,
            "data": {
                "session_id": "xyz789",
                ...
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        initial_capital = float(data.get('initial_capital', 10000.0))
        
        game_service = get_game_service()
        
        if session_id:
            game_service.reset_game(session_id)
        
        result = game_service.start_new_game(initial_capital)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 重置游戏失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/state', methods=['GET'])
def get_state():
    """
    获取当前游戏状态
    
    Query Params:
        session_id: 会话ID
    
    Response:
        {
            "success": true,
            "data": {
                "session_id": "...",
                "stock_code": "...",
                "stock_name": "...",
                "history_klines": [...],
                "trade_klines": [...],
                "current_kline": {...},
                "statistics": {...},
                "trades": [...]
            }
        }
    """
    try:
        session_id = request.args.get('session_id')
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        game_service = get_game_service()
        result = game_service.get_game_state(session_id)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 获取状态失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/change_stock', methods=['POST'])
def change_stock():
    """
    换股功能：保留统计指标，切换到另一只股票
    
    Request Body:
        {
            "session_id": "abc123"
        }
    
    Response:
        {
            "success": true,
            "data": {
                "stock_code": "新股票代码",
                "stock_name": "新股票名称",
                "history_klines": [...],
                "current_kline": {...},
                "statistics": {...}  // 保留累计统计
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        volatility_filter = data.get('volatility_filter', 'random')
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        if volatility_filter not in ['random', 'high', 'extreme']:
            volatility_filter = 'random'
        
        game_service = get_game_service()
        result = game_service.change_stock(session_id, volatility_filter)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 换股失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)


@game_bp.route('/end', methods=['POST'])
def end_game():
    """
    提前结束游戏
    
    Request Body:
        {
            "session_id": "abc123"
        }
    
    Response:
        {
            "success": true,
            "data": {
                "final_assets": 12000.0,
                "statistics": {...}
            }
        }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return json_response({
                "success": False,
                "error": "缺少 session_id"
            }, status_code=400)
        
        game_service = get_game_service()
        result = game_service.end_game(session_id)
        
        return json_response(result)
        
    except Exception as e:
        logger.error(f"[GameAPI] 结束游戏失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": str(e)
        }, status_code=500)
