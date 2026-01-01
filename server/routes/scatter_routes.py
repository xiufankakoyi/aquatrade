"""
散点图相关路由
"""
from flask import Blueprint, request, jsonify
import concurrent.futures
from config.logger import get_logger

scatter_bp = Blueprint('scatter', __name__, url_prefix='/api')
logger = get_logger(__name__)


@scatter_bp.route('/scatter_data', methods=['GET'])
def get_scatter_data():
    """获取情感-热度散点图数据 - 重构后：委托给 visualization_api"""
    # 延迟导入避免循环依赖
    from server.app import get_api
    
    try:
        symbol = request.args.get('symbol')
        logger.info(f"开始获取散点图数据: symbol={symbol}")
        
        # 【性能优化】使用异步执行，避免阻塞主线程
        # 注意：Flask 本身不支持真正的异步，但使用线程池可以避免阻塞
        
        def execute_query():
            """在单独线程中执行查询"""
            return get_api().get_scatter_data(symbol)
        
        # 【性能优化】使用线程池执行，设置超时控制
        # 优化：使用更小的超时时间（30秒），因为已经优化了查询逻辑
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute_query)
            try:
                result = future.result(timeout=30.0)  # 30秒超时（已优化查询，应该更快）
                logger.info(f"散点图数据获取成功: {len(result.get('data', []))} 条记录")
                return jsonify(result)
            except concurrent.futures.TimeoutError:
                logger.warning("散点图数据查询超时（超过30秒）")
                return jsonify({
                    'success': False,
                    'error': '查询超时，数据量较大，请稍后重试或指定具体股票代码',
                    'data': []
                }), 504
    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
        # CHANGED: 特别处理连接错误，这是客户端超时关闭连接导致的
        logger.debug(f"客户端连接已关闭（散点图数据）: {type(e).__name__}")
        # 连接已关闭，无法返回响应，返回 None 让 Flask 正常处理
        return None
    except Exception as e:
        logger.error(f"获取散点图数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500

