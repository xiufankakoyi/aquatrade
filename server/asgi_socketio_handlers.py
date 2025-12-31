# server/asgi_socketio_handlers.py
"""
ASGI SocketIO 事件处理器

将原有的 Flask-SocketIO 事件处理器转换为异步版本
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from typing import Dict, Any
import asyncio

# 导入必要的模块
from server.performance_utils import pack_backtest_data
from utils.binary_packer import pack_backtest_result, estimate_size

try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    msgpack = None


def register_handlers(sio):
    """
    注册所有 SocketIO 事件处理器（异步版本）
    
    Args:
        sio: socketio.AsyncServer 实例
    """
    from config.logger import get_logger
    logger = get_logger(__name__)
    
    # 存储活跃的回测任务
    active_backtests: Dict[str, Any] = {}
    
    @sio.event
    async def connect(sid, environ):
        """客户端连接事件"""
        try:
            logger.debug(f"Socket.IO 客户端已连接: {sid}")
        except Exception as e:
            logger.error(f"Socket.IO 连接处理失败: {e}")
    
    @sio.event
    async def disconnect(sid):
        """客户端断开事件"""
        try:
            logger.debug(f"Socket.IO 客户端已断开: {sid}")
            # 清理活跃的回测任务
            if sid in active_backtests:
                stop_event = active_backtests[sid]
                stop_event.set()
                del active_backtests[sid]
        except Exception as e:
            logger.error(f"Socket.IO 断开处理失败: {e}")
    
    @sio.event
    async def run_streaming_backtest(sid, data):
        """
        运行流式回测（异步版本）
        
        注意：回测逻辑本身可能还是同步的，需要在后台线程中运行
        """
        from threading import Event
        from server.visualization_api import BacktestVisualizationAPI
        from config.logger import get_logger
        
        logger = get_logger(__name__)
        
        # #region agent log
        import json, time
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_streaming_backtest","message":"收到 run_streaming_backtest 事件","data":{"sid":sid,"data_keys":list(data.keys()) if isinstance(data, dict) else str(type(data))},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
        except: pass
        # #endregion
        
        try:
            strategy_name = data.get('strategy_name')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            benchmark_code = data.get('benchmark_code', '000300')
            profile_id = data.get('profile_id')
            override_params = data.get('override_params') or {}
            
            if not all([strategy_name, start_date, end_date]):
                await sio.emit('backtest_error', {
                    "message": "缺少必需参数: strategy_name, start_date, end_date"
                }, room=sid)
                return
            
            # 处理 profile_id（如果提供）
            effective_params = None
            if profile_id is not None:
                try:
                    from core.profiles.profile_repository import get_profile as load_profile
                    profile = load_profile(int(profile_id))
                    if profile is None:
                        await sio.emit('backtest_error', {
                            "message": f"Profile {profile_id} 不存在"
                        }, room=sid)
                        return
                    params_from_profile = profile.get("params") or {}
                    if not isinstance(params_from_profile, dict):
                        params_from_profile = {}
                    if not isinstance(override_params, dict):
                        override_params = {}
                    effective_params = {**params_from_profile, **override_params}
                except Exception as e:
                    await sio.emit('backtest_error', {
                        "message": f"加载 Profile 失败: {e}"
                    }, room=sid)
                    return
            else:
                effective_params = override_params if override_params else None
            
            # 创建停止事件
            stop_event = Event()
            active_backtests[sid] = stop_event
            
            # 发送确认消息
            await sio.emit('request_received', {"message": "回测请求已收到"}, room=sid)
            
            # 在后台线程中运行回测（因为回测逻辑可能是同步的）
            # 使用 asyncio.to_thread 或 run_in_executor
            loop = asyncio.get_event_loop()
            
            # 运行回测（在后台线程中）
            def run_backtest():
                # #region agent log
                import json, time
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"开始执行回测","data":{"strategy_name":strategy_name,"start_date":start_date,"end_date":end_date},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                except: pass
                # #endregion
                
                try:
                    logger.info(f"开始流式回测: {strategy_name} | {start_date}~{end_date} | 基准: {benchmark_code}")
                    print(f"[BACKTEST] 开始流式回测: {strategy_name} | {start_date}~{end_date} | 基准: {benchmark_code}")
                    
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"创建 BacktestVisualizationAPI","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                    except: pass
                    # #endregion
                    
                    print(f"[BACKTEST] 创建 BacktestVisualizationAPI 实例...")
                    api = BacktestVisualizationAPI()
                    print(f"[BACKTEST] 初始化 API...")
                    api._ensure_initialized()
                    print(f"[BACKTEST] API 初始化完成，开始调用 stream_backtest...")
                    
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"开始调用 stream_backtest","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                    except: pass
                    # #endregion
                    
                    # 运行流式回测（使用正确的方法名 stream_backtest）
                    print(f"[BACKTEST] 调用 stream_backtest: {strategy_name}, {start_date}~{end_date}")
                    update_count = 0
                    last_update_time = time.time()
                    generator = api.stream_backtest(
                        strategy_name=strategy_name,
                        start_date=start_date,
                        end_date=end_date,
                        benchmark_code=benchmark_code,
                        stop_event=stop_event,
                        params=effective_params
                    )
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"generator创建完成，开始迭代","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"E"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
                    for update in generator:
                        # #region agent log
                        if update_count == 0:
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"开始迭代generator，收到第一个update","data":{"type":update.get('type') if isinstance(update, dict) else str(type(update))},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"E"}) + "\n")
                                    f.flush()
                            except: pass
                        # #endregion
                        # 检查超时（如果超过30秒没有更新，记录警告）
                        current_time = time.time()
                        if current_time - last_update_time > 30:
                            # #region agent log
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"回测更新超时警告","data":{"last_update":update_count,"elapsed":current_time-last_update_time},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"L"}) + "\n")
                            except: pass
                            # #endregion
                            print(f"[BACKTEST WARN] 超过30秒没有收到更新，最后更新: {update_count}")
                        last_update_time = current_time
                        update_count += 1
                        if update_count == 1:
                            print(f"[BACKTEST] 收到第一个回测更新: {update.get('type')}")
                        if update_count % 10 == 0:
                            print(f"[BACKTEST] 已处理 {update_count} 个更新...")
                        if update_count == 1:
                            # #region agent log
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"收到第一个回测更新","data":{"update_type":update.get('type')},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                            except: pass
                            # #endregion
                        if stop_event.is_set():
                            break
                        
                        # 发送更新（需要在异步上下文中发送）
                        t = update.get('type')
                        update_data = update.get('data', {})
                        
                        # 创建发送任务的辅助函数
                        async def send_update(event_name, payload):
                            # #region agent log
                            import json, time
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_update","message":"开始发送事件","data":{"event_name":event_name,"sid":sid,"has_payload":payload is not None},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"K"}) + "\n")
                                    f.flush()
                            except: pass
                            # #endregion
                            try:
                                await sio.emit(event_name, payload, room=sid)
                                # #region agent log
                                try:
                                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_update","message":"事件发送完成","data":{"event_name":event_name,"sid":sid},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"K"}) + "\n")
                                        f.flush()
                                except: pass
                                # #endregion
                            except Exception as e:
                                # #region agent log
                                try:
                                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_update","message":"事件发送异常","data":{"event_name":event_name,"sid":sid,"error":str(e),"type":type(e).__name__},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"K"}) + "\n")
                                        f.flush()
                                except: pass
                                # #endregion
                                logger.error(f"发送事件 {event_name} 失败: {e}")
                                raise
                        
                        if t == 'error':
                            asyncio.run_coroutine_threadsafe(
                                send_update('backtest_error', update_data),
                                loop
                            )
                            return
                        elif t == 'cancelled':
                            asyncio.run_coroutine_threadsafe(
                                send_update('backtest_cancelled', update_data or {"message": "回测已取消"}),
                                loop
                            )
                            return
                        elif t == 'backtest_start':
                            asyncio.run_coroutine_threadsafe(
                                send_update('backtest_start', update_data),
                                loop
                            )
                        elif t == 'progress':
                            asyncio.run_coroutine_threadsafe(
                                send_update('progress', update_data),
                                loop
                            )
                        elif t == 'initializing':
                            # #region agent log
                            import json, time
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_initializing","message":"准备发送 initializing 事件","data":{"sid":sid,"update_data_keys":list(update_data.keys()) if isinstance(update_data, dict) else "not_dict"},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                                    f.flush()
                            except: pass
                            # #endregion
                            future = asyncio.run_coroutine_threadsafe(
                                send_update('initializing', update_data),
                                loop
                            )
                            # #region agent log
                            try:
                                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_initializing","message":"已调用 run_coroutine_threadsafe 发送 initializing","data":{"sid":sid,"future_done":future.done()},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                                    f.flush()
                            except: pass
                            # #endregion
                            # 等待一小段时间，检查是否有异常
                            try:
                                future.result(timeout=0.1)  # 100ms 超时
                                # #region agent log
                                try:
                                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_initializing","message":"initializing 事件发送成功","data":{"sid":sid},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                                        f.flush()
                                except: pass
                                # #endregion
                            except Exception as e:
                                # #region agent log
                                try:
                                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:send_initializing","message":"initializing 事件发送失败","data":{"sid":sid,"error":str(e),"type":type(e).__name__},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                                        f.flush()
                                except: pass
                                # #endregion
                                logger.error(f"发送 initializing 事件失败: {e}")
                        elif t == 'initialized':
                            asyncio.run_coroutine_threadsafe(
                                send_update('initialized', update_data),
                                loop
                            )
                        elif t == 'daily_equity':
                            # 映射为前端监听的 daily_update
                            # 使用 MsgPack 打包
                            if isinstance(update_data, dict):
                                try:
                                    packed = pack_backtest_result(update_data)
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('daily_update', {
                                            '_msgpack': True,
                                            '_data': packed
                                        }),
                                        loop
                                    )
                                except Exception as e:
                                    logger.warning(f"MsgPack 打包失败: {e}")
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('daily_update', update_data),
                                        loop
                                    )
                            else:
                                asyncio.run_coroutine_threadsafe(
                                    send_update('daily_update', update_data),
                                    loop
                                )
                        elif t == 'new_trade':
                            asyncio.run_coroutine_threadsafe(
                                send_update('new_trade', update_data),
                                loop
                            )
                        elif t == 'final_metrics':
                            # 使用 MsgPack 打包
                            if isinstance(update_data, dict):
                                try:
                                    packed = pack_backtest_result(update_data)
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('metrics_update', {
                                            '_msgpack': True,
                                            '_data': packed
                                        }),
                                        loop
                                    )
                                except Exception as e:
                                    logger.warning(f"MsgPack 打包失败: {e}")
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('metrics_update', update_data),
                                        loop
                                    )
                            else:
                                asyncio.run_coroutine_threadsafe(
                                    send_update('metrics_update', update_data),
                                    loop
                                )
                        elif t == 'risk_data':
                            # 使用 MsgPack 打包
                            if isinstance(update_data, dict):
                                try:
                                    packed = pack_backtest_result(update_data)
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('risk_update', {
                                            '_msgpack': True,
                                            '_data': packed
                                        }),
                                        loop
                                    )
                                except Exception as e:
                                    logger.warning(f"MsgPack 打包失败: {e}")
                                    asyncio.run_coroutine_threadsafe(
                                        send_update('risk_update', update_data),
                                        loop
                                    )
                            else:
                                asyncio.run_coroutine_threadsafe(
                                    send_update('risk_update', update_data),
                                    loop
                                )
                        elif t == 'stream_complete':
                            asyncio.run_coroutine_threadsafe(
                                send_update('stream_complete', {"message": "回测完成"}),
                                loop
                            )
                            return
                except Exception as e:
                    # #region agent log
                    import traceback
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"回测执行异常","data":{"error":str(e),"traceback":traceback.format_exc()[:500]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                    except: pass
                    # #endregion
                    print(f"[BACKTEST ERROR] 回测失败: {e}")
                    import traceback
                    print(f"[BACKTEST ERROR] 异常堆栈:\n{traceback.format_exc()}")
                    logger.error(f"回测失败: {e}", exc_info=True)
                    asyncio.run_coroutine_threadsafe(
                        sio.emit('backtest_error', {"message": str(e)}, room=sid),
                        loop
                    )
                finally:
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_backtest","message":"回测执行完成（finally）","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
                    except: pass
                    # #endregion
                    if sid in active_backtests:
                        del active_backtests[sid]
            
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_streaming_backtest","message":"准备在后台线程中运行回测","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
            except: pass
            # #endregion
            
            # 在后台线程中运行
            await loop.run_in_executor(None, run_backtest)
            
        except Exception as e:
            # #region agent log
            import traceback
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"asgi_socketio_handlers.py:run_streaming_backtest","message":"启动回测失败（外层异常）","data":{"error":str(e),"traceback":traceback.format_exc()[:500]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"F"}) + "\n")
            except: pass
            # #endregion
            logger.error(f"启动回测失败: {e}", exc_info=True)
            await sio.emit('backtest_error', {"message": str(e)}, room=sid)
            if sid in active_backtests:
                del active_backtests[sid]
    
    @sio.event
    async def cancel_streaming_backtest(sid, data=None):
        """取消回测（异步版本）"""
        if sid in active_backtests:
            stop_event = active_backtests[sid]
            stop_event.set()
            await sio.emit('backtest_cancel_ack', {"message": "正在停止回测..."}, room=sid)
            del active_backtests[sid]
        else:
            await sio.emit('backtest_cancel_ack', {"message": "当前没有正在运行的回测"}, room=sid)
    
    logger.info("ASGI SocketIO 事件处理器已注册")

