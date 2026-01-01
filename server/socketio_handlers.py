"""
Socket.IO 事件处理器
"""
import os
from threading import Event
from flask import request
from flask_socketio import emit
# 延迟导入避免循环依赖
from utils.binary_packer import pack_backtest_result, estimate_size
from config.logger import get_logger

logger = get_logger(__name__)


def register_socketio_handlers(socketio_instance):
    """
    注册所有 Socket.IO 事件处理器
    
    Args:
        socketio_instance: SocketIO 实例（从 server.app 传入）
    """
    # 延迟导入避免循环依赖
    from server.app import (
        get_api, active_backtests, active_optimizations
    )
    from server.logic.backtest import run_backtest_background, _emit_large_data
    @socketio_instance.on('connect')
    def handle_connect():
        """【健壮性加固】SocketIO 连接事件，添加异常捕获"""
        try:
            # 只在 DEBUG 模式下输出连接信息
            debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
            if debug_mode:
                logger.debug(f"Socket.IO 客户端已连接: {request.sid}")
        except Exception as e:
            logger.error(f"Socket.IO 连接处理失败: {e}")

    @socketio_instance.on('disconnect')
    def handle_disconnect():
        """【健壮性加固】SocketIO 断开事件，添加异常捕获"""
        try:
            # 只在 DEBUG 模式下输出断开信息
            debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
            if debug_mode:
                logger.debug(f"Socket.IO 客户端已断开: {request.sid}")
        except Exception as e:
            logger.error(f"Socket.IO 断开处理失败: {e}")

    @socketio_instance.on('run_streaming_backtest')
    def handle_streaming_backtest(data):
        """
        这里只负责解析前端传来的参数，然后启动后台任务
        """
        try:
            strategy_name = data.get('strategy_name')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            benchmark_code = data.get('benchmark_code')
            profile_id = data.get('profile_id')
            override_params = data.get('override_params') or {}

            if not all([strategy_name, start_date, end_date]):
                emit('backtest_error', {"message": "缺少必要参数"})
                return

            # 如果带 profile_id，则在这里加载并合并参数，传入 API
            effective_params = None
            if profile_id is not None:
                try:
                    from core.profiles.profile_repository import get_profile as load_profile

                    profile = load_profile(int(profile_id))
                    if profile is None:
                        emit('backtest_error', {"message": f"Profile {profile_id} 不存在"})
                        return
                    params_from_profile = profile.get("params") or {}
                    if not isinstance(params_from_profile, dict):
                        params_from_profile = {}
                    if not isinstance(override_params, dict):
                        override_params = {}
                    effective_params = {**params_from_profile, **override_params}
                except Exception as e:
                    emit('backtest_error', {"message": f"加载 Profile 失败: {e}"})
                    return

            print(f"📨 收到流式回测请求: {strategy_name} | {start_date}~{end_date} | 基准: {benchmark_code or 'None'}")

            # 当前这位前端用户的 sid
            sid = request.sid

            # 给前端一个"我收到了"的反馈（你 App.vue 有监听）
            emit('request_received', {"message": "回测请求已收到"})

            # 启动后台任务，不阻塞当前事件 handler
            stop_event = Event()
            active_backtests[sid] = stop_event

            # 传递 socketio 实例和必要的依赖
            socketio_instance.start_background_task(
                run_backtest_background,
                socketio_instance,  # 传递 socketio 实例
                sid, strategy_name, start_date, end_date, benchmark_code, stop_event, effective_params,
                get_api,  # 传递 get_api 函数
                active_backtests  # 传递 active_backtests 字典
            )

        except Exception as e:
            print("❌ 流式回测启动失败:", e)
            emit('backtest_error', {"message": str(e)})

    @socketio_instance.on('cancel_streaming_backtest')
    def handle_cancel_backtest(data=None):
        """
        处理取消回测请求
        CHANGED: 接受 data 参数（即使不使用），避免 Socket.IO 参数不匹配错误
        """
        sid = request.sid
        stop_event = active_backtests.get(sid)
        if stop_event:
            stop_event.set()
            emit('backtest_cancel_ack', {"message": "正在停止回测..."})
            logger.info(f"收到取消回测请求，已设置停止标志 (sid: {sid})")
        else:
            emit('backtest_cancel_ack', {"message": "当前没有正在运行的回测"})
            logger.warning(f"收到取消回测请求，但当前没有运行的回测 (sid: {sid})")

    @socketio_instance.on('request_kline')
    def handle_request_kline(data):
        symbol_code = data.get('symbol_code')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not symbol_code:
            emit('kline_data', {"error": "缺少 symbol_code"}, to=request.sid)
            return

        print(f"📈 请求 K 线 {symbol_code} | {start_date} ~ {end_date}")
        api_instance = get_api()
        history = api_instance.get_symbol_kline(symbol_code, start_date, end_date)
        emit('kline_data', {
            "request_id": data.get('request_id'),
            "symbol_code": symbol_code,
            "data": history
        }, to=request.sid)

    @socketio_instance.on('stop_optimization')
    def handle_stop_optimization(data):
        """处理停止优化请求"""
        request_sid = request.sid
        # 优先使用前端显式传来的 sid（表示真正运行优化的会话）
        target_sid = None
        try:
            if isinstance(data, dict):
                target_sid = data.get("sid") or data.get("session_id")
        except Exception:
            target_sid = None
        if not target_sid:
            target_sid = request_sid

        if target_sid in active_optimizations:
            # 设置停止事件
            active_optimizations[target_sid].set()
            emit('optimization_cancel_ack', {"message": "正在停止优化..."})
            logger.info(f"收到取消优化请求，已设置停止标志 (sid: {target_sid})")
        else:
            emit('optimization_cancel_ack', {"message": "当前没有正在运行的优化"})
            logger.warning(f"收到取消优化请求，但当前没有运行的优化 (请求来自 sid: {request_sid}, 目标 sid: {target_sid})")

    @socketio_instance.on('run_optimization')
    def handle_run_optimization(data):
        """处理参数优化请求（支持新旧两种格式）"""
        try:
            sid = request.sid
            
            # 检查是否是新格式（包含 optimization_engine 和 search_space）
            if 'optimization_engine' in data and 'search_space' in data:
                # 新格式处理
                strategy_name = data.get('strategy_name')
                optimization_engine = data.get('optimization_engine', {})
                search_space = data.get('search_space', [])
                objective = data.get('objective', {})
                backtest = data.get('backtest', {})
                validation = data.get('validation', {})

                # 全局优化模式（quick_explore / robust / aggressive）
                mode = data.get('mode') or validation.get('mode') or 'robust'
                
                method = optimization_engine.get('method', 'ga')
                # 统一方法名称（前端可能发送 cmaes，后端期望 cma_es）
                if method == 'cmaes':
                    method = 'cma_es'
                algo_params = optimization_engine.get('params', {})
                
                start_date = backtest.get('start_date') or data.get('start_date')
                end_date = backtest.get('end_date') or data.get('end_date')
                
                if not all([strategy_name, start_date, end_date]):
                    emit('optimization_error', {"message": "缺少必要参数: strategy_name, start_date, end_date"})
                    return
                
                print(f"🔍 收到参数优化请求（新格式）: {strategy_name} | {start_date}~{end_date}")
                print(f"   算法: {method} | 参数: {algo_params}")
                print(f"   搜索空间: {len(search_space)} 个参数")
                
                # 构建 param_ranges（从 search_space 转换）
                param_ranges = []
                for param_spec in search_space:
                    param_name = param_spec.get('name')
                    param_type = param_spec.get('type', 'float')
                    param_min = param_spec.get('min')
                    param_max = param_spec.get('max')
                    
                    if not all([param_name, param_min is not None, param_max is not None]):
                        logger.warning(f"跳过无效参数: {param_spec}")
                        continue
                    
                    lower, upper = float(param_min), float(param_max)
                    
                    # 验证参数范围
                    if lower >= upper:
                        logger.warning(f"参数范围验证失败: {param_name} 范围 [{lower}, {upper}] 无效，将使用安全范围")
                        lower, upper = min(lower, upper - 1), max(upper, lower + 1)
                    
                    param_range = {
                        "name": param_name,
                        "bounds": [lower, upper],
                        "type": param_type
                    }
                    
                    # 网格搜索需要步长
                    if method == 'grid' and 'step' in param_spec:
                        param_range['step'] = float(param_spec['step'])
                    
                    param_ranges.append(param_range)
                    print(f"📊 参数范围设置: {param_name} = [{lower}, {upper}] ({param_type})")
                
                if not param_ranges:
                    emit('optimization_error', {"message": "没有有效的参数范围定义"})
                    return
                
                # 构建优化配置（转换为后端期望的格式）
                target_metric = objective.get('target', 'sharpe_ratio')
                # 转换指标名称
                metric_mapping = {
                    'sharpe_ratio': 'sharpe_ratio',
                    'total_return': 'total_return',
                    'max_drawdown': 'max_drawdown',
                    'win_rate': 'win_rate',
                    'calmar_ratio': 'calmar_ratio'
                }
                target_metric = metric_mapping.get(target_metric, 'sharpe_ratio')
                
                # 启动优化任务（使用新的优化引擎）
                from core.optimization.optimization_engine import OptimizationEngine
                engine = OptimizationEngine()
                
                stop_event = Event()
                active_optimizations[sid] = stop_event
                
                # 启动后台任务
                def run_optimization_background():
                    try:
                        engine.run_optimization_streaming(
                            strategy_name=strategy_name,
                            start_date=start_date,
                            end_date=end_date,
                            param_ranges=param_ranges,
                            method=method,
                            algo_params=algo_params,
                            target_metric=target_metric,
                            mode=mode,
                            socketio=socketio_instance,
                            sid=sid,
                            stop_event=stop_event
                        )
                    except Exception as e:
                        logger.error(f"优化任务失败: {e}", exc_info=True)
                        socketio_instance.emit('optimization_error', {"message": str(e)}, to=sid)
                    finally:
                        active_optimizations.pop(sid, None)
                
                socketio_instance.start_background_task(run_optimization_background)
                emit('optimization_started', {"message": "优化任务已启动"})
                
            else:
                # 旧格式处理（向后兼容）
                strategy_name = data.get('strategy_name')
                param_ranges = data.get('param_ranges', [])
                start_date = data.get('start_date')
                end_date = data.get('end_date')
                method = data.get('method', 'ga')
                algo_params = data.get('algo_params', {})
                target_metric = data.get('target_metric', 'sharpe_ratio')
                
                if not all([strategy_name, start_date, end_date, param_ranges]):
                    emit('optimization_error', {"message": "缺少必要参数"})
                    return
                
                print(f"🔍 收到参数优化请求（旧格式）: {strategy_name} | {start_date}~{end_date}")
                
                from core.optimization.optimization_engine import OptimizationEngine
                engine = OptimizationEngine()
                
                stop_event = Event()
                active_optimizations[sid] = stop_event
                
                def run_optimization_background():
                    try:
                        engine.run_optimization_streaming(
                            strategy_name=strategy_name,
                            start_date=start_date,
                            end_date=end_date,
                            param_ranges=param_ranges,
                            method=method,
                            algo_params=algo_params,
                            target_metric=target_metric,
                            socketio=socketio_instance,
                            sid=sid,
                            stop_event=stop_event
                        )
                    except Exception as e:
                        logger.error(f"优化任务失败: {e}", exc_info=True)
                        socketio_instance.emit('optimization_error', {"message": str(e)}, to=sid)
                    finally:
                        active_optimizations.pop(sid, None)
                
                socketio_instance.start_background_task(run_optimization_background)
                emit('optimization_started', {"message": "优化任务已启动"})
                
        except Exception as e:
            logger.error(f"处理优化请求失败: {e}", exc_info=True)
            emit('optimization_error', {"message": str(e)})

