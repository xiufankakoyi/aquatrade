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
        logger.debug(f"收到 run_streaming_backtest 事件: sid={sid}, data_keys={list(data.keys()) if isinstance(data, dict) else str(type(data))}")
        
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
                import time
                try:
                    logger.info(f"开始流式回测: {strategy_name} | {start_date}~{end_date} | 基准: {benchmark_code}")
                    
                    api = BacktestVisualizationAPI()
                    api._ensure_initialized()
                    
                    # 运行流式回测
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
                    
                    # ==============================================================================
                    # 【消息批处理/限流优化】实现缓冲发送机制，避免消息推送过载
                    # 原问题：逐条发送导致网络拥塞和事件循环压力
                    # 解决方案：使用缓冲池，每 100ms 或满 50条 发送一次
                    # ==============================================================================
                    BATCH_INTERVAL = 0.1  # 100ms 批处理间隔
                    BATCH_SIZE = 50  # 每批最多 50 条消息
                    
                    # 缓冲池：按事件类型分类缓冲
                    buffers = {
                        'daily_equity': [],  # 每日权益数据
                        'new_trade': [],     # 交易数据
                        'signal': [],        # 信号数据
                    }
                    last_batch_send_time = time.time()
                    
                    # 立即发送的事件类型（不缓冲）
                    immediate_events = {
                        'error', 'cancelled', 'backtest_start', 'initializing', 
                        'initialized', 'final_metrics', 'risk_data', 'stream_complete',
                        'progress', 'backtest_end'
                    }
                    
                    def flush_buffers():
                        """刷新所有缓冲池，发送积攒的消息"""
                        nonlocal last_batch_send_time
                        # 事件类型到前端事件名称的映射
                        event_name_map = {
                            'daily_equity': 'daily_update',  # 前端期望的事件名称
                            'new_trade': 'new_trade',
                            'signal': 'signal'
                        }
                        
                        for event_type, buffer in buffers.items():
                            if buffer:
                                try:
                                    # 【数据序列化优化】确保核心数据路径使用严格定义的结构
                                    # 对于高频事件（daily_equity, new_trade），优先使用 MsgPack
                                    if MSGPACK_AVAILABLE and event_type in ['daily_equity', 'new_trade']:
                                        try:
                                            # 确保 buffer 是列表且每个元素都是字典
                                            if isinstance(buffer, list) and all(isinstance(item, dict) for item in buffer):
                                                packed = pack_backtest_result(buffer)
                                                frontend_event = event_name_map.get(event_type, event_type)
                                                asyncio.run_coroutine_threadsafe(
                                                    sio.emit(frontend_event, {
                                                        '_msgpack': True,
                                                        '_data': packed,
                                                        '_count': len(buffer),
                                                        '_batch': True  # 标记为批量消息
                                                    }, room=sid),
                                                    loop
                                                )
                                            else:
                                                # 数据结构不符合预期，回退到 JSON
                                                logger.warning(f"批量数据格式不符合预期 ({event_type}): 期望 list[dict], 实际: {type(buffer)}")
                                                frontend_event = event_name_map.get(event_type, event_type)
                                                asyncio.run_coroutine_threadsafe(
                                                    sio.emit(frontend_event, buffer, room=sid),
                                                    loop
                                                )
                                        except Exception as e:
                                            logger.warning(f"MsgPack 批量打包失败 ({event_type}): {e}")
                                            # 回退到 JSON
                                            frontend_event = event_name_map.get(event_type, event_type)
                                            asyncio.run_coroutine_threadsafe(
                                                sio.emit(frontend_event, buffer, room=sid),
                                                loop
                                            )
                                    else:
                                        # 直接发送 JSON（信号等低频事件）
                                        frontend_event = event_name_map.get(event_type, event_type)
                                        asyncio.run_coroutine_threadsafe(
                                            sio.emit(frontend_event, buffer, room=sid),
                                            loop
                                        )
                                    buffer.clear()
                                except Exception as e:
                                    logger.error(f"发送批量消息失败 ({event_type}): {e}", exc_info=True)
                        last_batch_send_time = time.time()
                    
                    for update in generator:
                        # 检查超时（如果超过30秒没有更新，记录警告）
                        current_time = time.time()
                        if current_time - last_update_time > 30:
                            logger.warning(f"回测更新超时警告: 最后更新={update_count}, 耗时={current_time - last_update_time:.1f}s")
                        last_update_time = current_time
                        update_count += 1
                        
                        if stop_event.is_set():
                            # 停止前刷新所有缓冲
                            flush_buffers()
                            break
                        
                        # 发送更新（需要在异步上下文中发送）
                        t = update.get('type')
                        update_data = update.get('data', {})
                        
                        # 创建发送任务的辅助函数（优化：移除所有 debug.log 写入）
                        async def send_update(event_name, payload):
                            try:
                                await sio.emit(event_name, payload, room=sid)
                            except Exception as e:
                                logger.error(f"发送事件 {event_name} 失败: {e}", exc_info=True)
                                raise
                        
                        # ==============================================================================
                        # 【消息批处理/限流优化】根据事件类型决定是否缓冲
                        # ==============================================================================
                        # 立即发送的事件（关键事件，不缓冲）
                        # 立即发送的事件（关键事件，不缓冲）
                        if t == 'error':
                            asyncio.run_coroutine_threadsafe(
                                send_update('backtest_error', update_data),
                                loop
                            )
                            flush_buffers()  # 停止前刷新缓冲
                            return
                        elif t == 'cancelled':
                            asyncio.run_coroutine_threadsafe(
                                send_update('backtest_cancelled', update_data or {"message": "回测已取消"}),
                                loop
                            )
                            flush_buffers()  # 停止前刷新缓冲
                            return
                        elif t in immediate_events:
                            # 立即发送关键事件
                            if t == 'backtest_start':
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
                                future = asyncio.run_coroutine_threadsafe(
                                    send_update('initializing', update_data),
                                    loop
                                )
                                try:
                                    future.result(timeout=0.1)  # 100ms 超时
                                except Exception as e:
                                    logger.error(f"发送 initializing 事件失败: {e}")
                            elif t == 'initialized':
                                asyncio.run_coroutine_threadsafe(
                                    send_update('initialized', update_data),
                                    loop
                                )
                            elif t == 'final_metrics':
                                # 【数据序列化优化】确保使用严格定义的结构
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
                                        logger.warning(f"MsgPack 打包失败，回退到 JSON: {e}")
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
                                # 【数据序列化优化】确保使用严格定义的结构
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
                                        logger.warning(f"MsgPack 打包失败，回退到 JSON: {e}")
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
                                flush_buffers()  # 完成前刷新所有缓冲
                                asyncio.run_coroutine_threadsafe(
                                    send_update('stream_complete', {"message": "回测完成"}),
                                    loop
                                )
                                return
                        
                        # ==============================================================================
                        # 【消息批处理/限流优化】高频事件使用缓冲池
                        # ==============================================================================
                        elif t == 'daily_equity_engine':
                            # 映射为 daily_equity，加入缓冲池
                            buffers['daily_equity'].append(update_data)
                            
                            # 检查是否需要刷新缓冲（时间间隔或数量阈值）
                            if (current_time - last_batch_send_time >= BATCH_INTERVAL or 
                                len(buffers['daily_equity']) >= BATCH_SIZE):
                                flush_buffers()
                        
                        elif t == 'daily_equity':
                            # 【修复】处理从 visualization_api.py 转换后的 daily_equity 事件
                            # visualization_api.py 已经将 daily_equity_engine 转换为 daily_equity
                            buffers['daily_equity'].append(update_data)
                            
                            # 调试：记录收到的 daily_equity 事件
                            if update_count <= 3 or update_count % 50 == 0:
                                logger.debug(f"[STREAM] 收到 daily_equity 事件 #{update_count}: date={update_data.get('date')}, equity={update_data.get('strategyReturn')}")
                            
                            # 检查是否需要刷新缓冲（时间间隔或数量阈值）
                            if (current_time - last_batch_send_time >= BATCH_INTERVAL or 
                                len(buffers['daily_equity']) >= BATCH_SIZE):
                                flush_buffers()
                        
                        elif t == 'new_trade_engine':
                            # 加入交易缓冲池
                            buffers['new_trade'].append(update_data)
                            
                            # 检查是否需要刷新缓冲
                            if (current_time - last_batch_send_time >= BATCH_INTERVAL or 
                                len(buffers['new_trade']) >= BATCH_SIZE):
                                flush_buffers()
                        
                        elif t == 'signal':
                            # 加入信号缓冲池
                            buffers['signal'].append(update_data)
                            
                            # 检查是否需要刷新缓冲
                            if (current_time - last_batch_send_time >= BATCH_INTERVAL or 
                                len(buffers['signal']) >= BATCH_SIZE):
                                flush_buffers()
                        
                        elif t == 'signal_batch':
                            # 【优化】处理批量信号事件，拆分为单个signal事件加入缓冲池
                            # 这样可以保持与现有批处理逻辑的兼容性
                            # update_data 应该是信号数组（batch_signals）
                            if isinstance(update_data, list):
                                for signal_item in update_data:
                                    buffers['signal'].append(signal_item)
                            else:
                                logger.warning(f"signal_batch 数据格式不正确: {type(update_data)}")
                            
                            # 检查是否需要刷新缓冲
                            if (current_time - last_batch_send_time >= BATCH_INTERVAL or 
                                len(buffers['signal']) >= BATCH_SIZE):
                                flush_buffers()
                        
                        else:
                            # 未知事件类型，记录警告但不阻塞
                            logger.debug(f"未知事件类型: {t}, 数据: {update_data}")
                        
                        # 定期刷新缓冲（即使未达到阈值）
                        if current_time - last_batch_send_time >= BATCH_INTERVAL:
                            flush_buffers()
                except Exception as e:
                    import traceback
                    logger.error(f"回测失败: {e}", exc_info=True)
                    # 停止前刷新所有缓冲
                    try:
                        flush_buffers()
                    except Exception:
                        pass
                    asyncio.run_coroutine_threadsafe(
                        sio.emit('backtest_error', {"message": str(e)}, room=sid),
                        loop
                    )
                finally:
                    # 确保所有缓冲都被刷新
                    try:
                        flush_buffers()
                    except Exception:
                        pass
                    if sid in active_backtests:
                        del active_backtests[sid]
            
            # 在后台线程中运行
            await loop.run_in_executor(None, run_backtest)
            
        except Exception as e:
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

