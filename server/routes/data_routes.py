"""
数据查询相关路由
"""
from flask import Blueprint, request
from server.performance_utils import json_response
from datetime import datetime
import time
from config.config import Config
from core.error_handler import ErrorHandler, ErrorLevel, capture_error

data_bp = Blueprint('data', __name__, url_prefix='/api')


@data_bp.route('/kline', methods=['GET'])
def get_kline_data():
    """
    HTTP 接口：返回指定标的在时间区间内的 K 线数据
    """
    from server.app import get_api
    
    symbol_code = request.args.get('symbol')
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if not symbol_code:
        return json_response({"success": False, "error": "缺少 symbol 参数"}, status_code=400)

    try:
        history = get_api().get_symbol_kline(symbol_code, start_date, end_date)
        return json_response({"success": True, "data": history})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


def _emit_progress(data):
    """
    兼容 ASGI 模式的进度发送函数
    
    使用 asyncio.run_coroutine_threadsafe 在后台线程中调用异步 emit
    使用广播模式（不指定 room）确保所有连接的客户端都能收到进度更新
    """
    try:
        import asyncio
        from server.asgi_entry import sio
        from config.logger import get_logger
        logger = get_logger(__name__)
        
        # 调试日志
        logger.info(f"[DataUpdate] 发送进度: {data}")
        
        # 获取或创建事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 使用广播模式发送事件（不指定 room，所有客户端都能收到）
        async def emit_broadcast():
            await sio.emit('db_update_progress', data)
            logger.debug(f"[DataUpdate] 进度事件已广播: {data.get('status', 'unknown')}")
        
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(emit_broadcast(), loop)
        else:
            loop.run_until_complete(emit_broadcast())
            
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.warning(f"[DataUpdate] 进度发送失败: {e}", exc_info=True)


@data_bp.route('/db/update', methods=['POST'])
def update_database():
    """
    触发数据库增量更新 (Tushare -> 目标数据库
    
    【修复】根据 DB_BACKEND 自动选择更新器：
    - duckdb/parquet: 使用 ParquetUpdater
    - lancedb: 使用 LanceDBUpdater
    - questdb: 使用 QuestDBUpdater
    """
    import threading
    import os
    from config.logger import get_logger
    logger = get_logger(__name__)
    
    logger.info("[DataUpdate] 收到数据库更新请求")
    
    def run_update_task():
        """
        后台线程执行更新任务，包含完整的错误捕获
        """
        try:
            _run_update_task_inner()
        except Exception as e:
            logger.error(f"[DataUpdate] 后台任务异常: {e}", exc_info=True)
            ErrorHandler.capture(e, level=ErrorLevel.CRITICAL, category="database", context={"task": "update_database"})
            try:
                _emit_progress({
                    "status": "FAILED",
                    "progress": 0,
                    "message": f"后台任务异常: {str(e)}"
                })
            except:
                pass

    def _run_update_task_inner():
        try:
            time.sleep(0.5)  # 等待 Socket.IO 连接建立
            db_backend = os.getenv("DB_BACKEND", "duckdb").lower()
            logger.info(f"[DataUpdate] 数据库后端: {db_backend}")
            
            if db_backend in ["duckdb", "parquet"]:
                from data_svc.database.parquet_updater import ParquetUpdater
                logger.info("[DataUpdate] 使用 ParquetUpdater")
                updater = ParquetUpdater(progress_callback=_emit_progress)
                result = updater.run_sync()
                logger.info(f"[DataUpdate] 任务完成: {result}")
            elif db_backend == "lancedb":
                from data_svc.database.lance_updater import LanceDBUpdater
                updater = LanceDBUpdater(progress_callback=_emit_progress)
                updater.run_sync()
            elif db_backend == "questdb":
                from data_svc.database.questdb_updater import QuestDBUpdater
                updater = QuestDBUpdater(progress_callback=_emit_progress)
                updater.run_sync()
            else:
                _emit_progress({
                    "status": "FAILED",
                    "progress": 0,
                    "message": f"不支持的数据库后端: {db_backend}"
                })
                return
            
        except ValueError as e:
            logger.error(f"配置错误: {e}")
            _emit_progress({
                "status": "FAILED",
                "progress": 0,
                "message": str(e)
            })
            ErrorHandler.capture(e, level=ErrorLevel.ERROR, category="database", context={"db_backend": db_backend})
        except ImportError as e:
            logger.error(f"依赖缺失: {e}")
            _emit_progress({
                "status": "FAILED",
                "progress": 0,
                "message": f"依赖缺失: {str(e)}"
            })
            ErrorHandler.capture(e, level=ErrorLevel.ERROR, category="database")
        except Exception as e:
            logger.error(f"Database update task failed: {e}", exc_info=True)
            _emit_progress({
                "status": "FAILED",
                "progress": 0,
                "message": f"更新失败: {str(e)}"
            })
            ErrorHandler.capture(e, level=ErrorLevel.ERROR, category="database", context={"db_backend": db_backend})

    thread = threading.Thread(target=run_update_task, daemon=True)
    thread.start()
    
    return json_response({"success": True, "message": "数据库更新任务已在后台启动"})


@data_bp.route('/latest_price', methods=['GET'])
def get_latest_price():
    """
    返回一个或多个标的的最新价格
    """
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


@data_bp.route('/db/last_date', methods=['GET'])
def get_db_last_date():
    """
    获取数据库中最新数据的日期
    
    Returns:
        {
            "success": True,
            "last_date": "2025-02-10",  # 格式: YYYY-MM-DD
            "trade_date": "20250210"    # 格式: YYYYMMDD
        }
    """
    import os
    from config.logger import get_logger
    logger = get_logger(__name__)
    
    try:
        db_backend = os.getenv("DB_BACKEND", "duckdb").lower()
        
        if db_backend in ["duckdb", "parquet"]:
            from data_svc.database.parquet_updater import ParquetUpdater
            updater = ParquetUpdater()
            last_date = updater._get_last_date()
            
            if last_date:
                # 转换格式: YYYYMMDD -> YYYY-MM-DD
                formatted_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"
                return json_response({
                    "success": True,
                    "last_date": formatted_date,
                    "trade_date": last_date
                })
            else:
                # 数据库为空，返回默认起始日期
                return json_response({
                    "success": True,
                    "last_date": "2025-01-01",
                    "trade_date": "20250101",
                    "message": "数据库为空，使用默认起始日期"
                })
        elif db_backend == "questdb":
            # QuestDB 实现
            from data_svc.database.questdb_updater import QuestDBUpdater
            updater = QuestDBUpdater()
            last_date = updater._get_last_date()
            
            if last_date:
                formatted_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"
                return json_response({
                    "success": True,
                    "last_date": formatted_date,
                    "trade_date": last_date
                })
            else:
                return json_response({
                    "success": True,
                    "last_date": "2025-01-01",
                    "trade_date": "20250101",
                    "message": "数据库为空，使用默认起始日期"
                })
        else:
            return json_response({
                "success": False,
                "error": f"不支持的数据库后端: {db_backend}"
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"获取数据库最新日期失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": f"获取数据库最新日期失败: {str(e)}"
        }, status_code=500)


@data_bp.route('/db/missing_dates', methods=['GET'])
def get_missing_dates():
    """
    获取指定时间范围内缺失的交易日期
    
    Query Args:
        start_date: 起始日期 (YYYY-MM-DD 或 YYYYMMDD)
        end_date: 结束日期 (YYYY-MM-DD 或 YYYYMMDD)，默认为今天
        
    Returns:
        {
            "success": True,
            "missing_dates": ["20250201", "20250205", ...],
            "missing_count": 5,
            "total_trade_days": 20,
            "coverage_rate": "75.0%"
        }
    """
    import os
    import pandas as pd
    from config.logger import get_logger
    logger = get_logger(__name__)
    
    try:
        # 获取参数
        start_date = request.args.get('start_date', '2025-01-01')
        end_date = request.args.get('end_date')
        
        # 标准化日期格式
        if '-' in start_date:
            start_date = start_date.replace('-', '')
        if end_date and '-' in end_date:
            end_date = end_date.replace('-', '')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"[MissingDates] 查询缺失日期: {start_date} 到 {end_date}")
        
        # 获取交易日历
        import tushare as ts
        ts.set_token(Config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        trade_cal = pro.trade_cal(exchange='', start_date=start_date, end_date=end_date)
        
        if trade_cal is None or trade_cal.empty:
            return json_response({
                "success": False,
                "error": "无法获取交易日历"
            }, status_code=500)
        
        # 获取所有交易日
        all_trade_dates = set(trade_cal['cal_date'].tolist())
        
        # 获取数据库中已有的日期
        db_backend = os.getenv("DB_BACKEND", "duckdb").lower()
        existing_dates = set()
        
        if db_backend in ["duckdb", "parquet"]:
            from data_svc.database.parquet_updater import ParquetUpdater
            updater = ParquetUpdater()
            existing_dates = updater._get_existing_dates()
        elif db_backend == "questdb":
            from data_svc.database.questdb_updater import QuestDBUpdater
            updater = QuestDBUpdater()
            existing_dates = updater._get_existing_dates()
        
        # 计算缺失的日期（在交易日历中但不在数据库中）
        missing_dates = sorted(list(all_trade_dates - existing_dates))
        
        # 计算覆盖率
        total_trade_days = len(all_trade_dates)
        missing_count = len(missing_dates)
        coverage_rate = ((total_trade_days - missing_count) / total_trade_days * 100) if total_trade_days > 0 else 0
        
        logger.info(f"[MissingDates] 发现 {missing_count} 个缺失日期，覆盖率: {coverage_rate:.1f}%")
        
        return json_response({
            "success": True,
            "missing_dates": missing_dates,
            "missing_count": missing_count,
            "total_trade_days": total_trade_days,
            "coverage_rate": f"{coverage_rate:.1f}%",
            "start_date": start_date,
            "end_date": end_date
        })
        
    except Exception as e:
        logger.error(f"获取缺失日期失败: {e}", exc_info=True)
        return json_response({
            "success": False,
            "error": f"获取缺失日期失败: {str(e)}"
        }, status_code=500)
