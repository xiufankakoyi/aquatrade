"""
数据查询相关路由
"""
from flask import Blueprint, request
from server.performance_utils import json_response

data_bp = Blueprint('data', __name__, url_prefix='/api')


@data_bp.route('/kline', methods=['GET'])
def get_kline_data():
    """
    HTTP 接口：返回指定标的在时间区间内的 K 线数据
    """
    # 延迟导入避免循环依赖
    from server.app import get_api
    
    symbol_code = request.args.get('symbol')
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if not symbol_code:
        return json_response({"success": False, "error": "缺少 symbol 参数"}, status_code=400)

    try:
        history = get_api().get_symbol_kline(symbol_code, start_date, end_date)
        return json_response(history)
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@data_bp.route('/latest_price', methods=['GET'])
def get_latest_price():
    """
    返回一个或多个标的的最新价格
    """
    # 延迟导入避免循环依赖
    from server.app import get_api
    
    symbol = request.args.get('symbol')
    symbols_param = request.args.get('symbols')
    target_date = request.args.get('date')

    symbol_list = []
    if symbols_param:
        symbol_list = [code.strip() for code in symbols_param.split(',') if code.strip()]
    elif symbol:
        symbol_list = [symbol.strip()]

    if not symbol_list:
        return json_response({"success": False, "error": "缺少 symbol/symbols 参数"}, status_code=400)

    try:
        latest_prices = get_api().get_latest_prices(symbol_list, target_date)
        return json_response(latest_prices)
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取最新价格失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)
