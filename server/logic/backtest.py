"""
回测业务逻辑
============

包含后台回测任务和相关的工具函数

【重构】流式序列化管道：
- 单次遍历：JSON 序列化 + Gzip 压缩一体化
- 启发式大小预判：O(1) 复杂度估算
- 内存视图复用：避免大块 bytes 深拷贝
- 异常阻断：安全关闭流缓冲
"""
import json
import gzip
import base64
import io
from typing import Dict, Any, List, Callable, Optional
from threading import Event
from contextlib import contextmanager
from config.logger import get_logger
from server.utils.binary_packer import (
    pack_backtest_result, 
    heuristic_estimate_size,
    stream_compress_to_base64,
    should_compress,
    StreamingJSONGzipEncoder
)

logger = get_logger(__name__)

COMPRESS_THRESHOLD = 1 * 1024 * 1024
CHUNK_THRESHOLD = 10 * 1024 * 1024
MAX_CHUNK_SIZE = 5 * 1024 * 1024


@contextmanager
def _safe_gzip_buffer():
    """
    安全的 Gzip 缓冲区上下文管理器
    
    确保异常时正确关闭流缓冲，避免内存泄漏。
    """
    buffer = io.BytesIO()
    gzip_file = None
    try:
        gzip_file = gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=6)
        yield buffer, gzip_file
    finally:
        if gzip_file is not None:
            try:
                gzip_file.close()
            except Exception:
                pass
        if buffer is not None:
            try:
                buffer.close()
            except Exception:
                pass


def _stream_compress_data(data: Any) -> str:
    """
    流式压缩数据为 Base64 字符串
    
    单次遍历完成 JSON 序列化 + Gzip 压缩 + Base64 编码。
    
    Args:
        data: 要压缩的数据（可 JSON 序列化）
        
    Returns:
        Base64 编码的压缩数据字符串
    """
    return stream_compress_to_base64(data)


def _chunk_large_array(arr: List[Any], chunk_size: int = 1000) -> List[List[Any]]:
    """将大数组分块"""
    return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]


def _emit_msgpack(socketio, sid: str, event_name: str, data: Dict[str, Any], 
                  fallback_func=None, log_size: bool = False) -> bool:
    """
    使用 MsgPack 打包并发送数据
    
    Args:
        socketio: SocketIO实例
        sid: 会话ID
        event_name: 事件名称
        data: 要发送的数据
        fallback_func: MsgPack失败时的回退函数
        log_size: 是否记录压缩比日志
    
    Returns:
        bool: 是否成功发送
    """
    if not isinstance(data, dict):
        if fallback_func:
            fallback_func(socketio, sid, event_name, data, logger)
        else:
            socketio.emit(event_name, data, to=sid)
        return True
    
    try:
        packed = pack_backtest_result(data)
        mv = memoryview(packed)
        packed_b64 = base64.b64encode(mv).decode('utf-8')
        
        if log_size:
            estimated = heuristic_estimate_size(data)
            logger.info(f"发送 {event_name} (MsgPack: {len(packed)} bytes, "
                       f"估算原始: {estimated / 1024 / 1024:.2f}MB)")
        
        socketio.emit(event_name, {
            '_msgpack': True,
            '_data': packed_b64
        }, to=sid)
        return True
    except Exception as e:
        logger.warning(f"MsgPack 打包失败，回退发送: {e}")
        if fallback_func:
            fallback_func(socketio, sid, event_name, data, logger)
        else:
            socketio.emit(event_name, data, to=sid)
        return False


def _emit_large_data(socketio, sid: str, event_name: str, data: Dict[str, Any], logger_instance):
    """
    【重构】大数据传输优化：流式压缩 + 启发式预判
    
    策略：
    1. 使用启发式估算（O(1)）判断数据大小
    2. 如果数据小于 1MB，直接发送
    3. 如果数据大于 1MB，使用流式压缩后发送
    4. 如果数据大于 10MB，分块发送
    
    Args:
        socketio: SocketIO实例
        sid: 会话ID
        event_name: 事件名称
        data: 要发送的数据
        logger_instance: 日志记录器
    """
    try:
        estimated_size = heuristic_estimate_size(data)
        size_mb = estimated_size / (1024 * 1024)
        
        if estimated_size < COMPRESS_THRESHOLD:
            socketio.emit(event_name, data, to=sid)
            logger_instance.debug(f"直接发送 {event_name} (估算: {size_mb:.2f}MB)")
        
        elif estimated_size < CHUNK_THRESHOLD:
            try:
                compressed_data = _stream_compress_data(data)
                socketio.emit(event_name, {
                    '_compressed': True,
                    '_data': compressed_data
                }, to=sid)
                logger_instance.info(
                    f"流式压缩发送 {event_name} (估算原始: {size_mb:.2f}MB, "
                    f"压缩后: {len(compressed_data) / 1024 / 1024:.2f}MB)"
                )
            except Exception as e:
                logger_instance.warning(f"流式压缩失败，回退到直接发送: {e}")
                socketio.emit(event_name, data, to=sid)
        
        else:
            large_arrays = {}
            other_data = {}
            
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 100:
                    large_arrays[key] = value
                else:
                    other_data[key] = value
            
            if not large_arrays:
                try:
                    compressed_data = _stream_compress_data(data)
                    socketio.emit(event_name, {
                        '_compressed': True,
                        '_data': compressed_data
                    }, to=sid)
                    logger_instance.info(f"流式压缩发送 {event_name} (估算原始: {size_mb:.2f}MB)")
                except Exception:
                    socketio.emit(event_name, data, to=sid)
                    logger_instance.warning(f"大数据直接发送 {event_name} (可能失败)")
            else:
                total_chunks = 0
                for key, arr in large_arrays.items():
                    chunks = _chunk_large_array(arr, chunk_size=1000)
                    total_chunks += len(chunks)
                    
                    socketio.emit(event_name, {
                        '_chunked': True,
                        '_key': key,
                        '_total_chunks': len(chunks),
                        '_chunk_index': 0,
                        '_other_data': other_data,
                        '_data': chunks[0] if chunks else []
                    }, to=sid)
                    
                    for idx, chunk in enumerate(chunks[1:], start=1):
                        socketio.sleep(0.01)
                        socketio.emit(event_name, {
                            '_chunked': True,
                            '_key': key,
                            '_total_chunks': len(chunks),
                            '_chunk_index': idx,
                            '_data': chunk
                        }, to=sid)
                
                logger_instance.info(f"分块发送 {event_name} (估算原始: {size_mb:.2f}MB, {total_chunks}块)")
    
    except Exception as e:
        logger_instance.error(f"发送大数据失败 {event_name}: {e}", exc_info=True)
        try:
            socketio.emit(event_name, data, to=sid)
        except Exception:
            logger_instance.error(f"直接发送也失败 {event_name}")


def _emit_streaming_compressed(
    socketio, 
    sid: str, 
    event_name: str, 
    data: Dict[str, Any],
    logger_instance
) -> bool:
    """
    【新增】流式压缩发送
    
    使用 StreamingJSONGzipEncoder 实现真正的流式处理：
    - JSON 序列化与 Gzip 压缩同时进行
    - 大对象只被遍历一次
    - 内存峰值显著降低
    
    Args:
        socketio: SocketIO 实例
        sid: 会话 ID
        event_name: 事件名称
        data: 要发送的数据
        logger_instance: 日志记录器
        
    Returns:
        是否成功发送
    """
    try:
        encoder = StreamingJSONGzipEncoder(data)
        compressed_b64 = encoder.encode_to_base64()
        
        socketio.emit(event_name, {
            '_compressed': True,
            '_data': compressed_b64
        }, to=sid)
        
        return True
        
    except Exception as e:
        logger_instance.error(f"流式压缩发送失败: {e}")
        return False


def run_backtest_background(
    socketio_instance,
    sid: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    benchmark_code: Optional[str],
    stop_event: Event,
    params: Optional[Dict[str, Any]] = None,
    backtest_config: Optional[Dict[str, Any]] = None,
    get_api_func: Optional[Callable] = None,
    active_backtests_dict: Optional[Dict[str, Event]] = None
):
    """
    在后台线程/协程里跑流式回测，并不断通过 socketio.emit 推送给前端
    
    Args:
        socketio_instance: SocketIO 实例（通过参数传递，避免循环依赖）
        sid: 会话ID
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        benchmark_code: 基准代码（可选）
        stop_event: 停止事件
        params: 策略参数（可选）
        get_api_func: 获取API实例的函数（可选，默认从 server.app 导入）
        active_backtests_dict: 活跃回测字典（可选，用于清理）
    """
    if get_api_func is None:
        from server.app import get_api
        get_api_func = get_api
    
    logger.info(f"开始流式回测: {strategy_name} | 基准: {benchmark_code or 'None'}")
    
    if backtest_config:
        logger.info(f"回测配置: {backtest_config}")

    try:
        for update in get_api_func().stream_backtest(
            strategy_name,
            start_date,
            end_date,
            benchmark_code,
            stop_event=stop_event,
            params=params,
            backtest_config=backtest_config,
        ):

            socketio_instance.sleep(0.001)

            t = update.get('type')
            data = update.get('data', {})

            if stop_event.is_set():
                try:
                    socketio_instance.emit('backtest_cancelled', {"message": "回测已取消"}, to=sid)
                except Exception:
                    pass
                break

            if t not in ['error', 'cancelled', 'backtest_start', 'progress', 'initializing', 'initialized', 
                         'daily_equity', 'new_trade', 'final_metrics', 'risk_data', 'stream_complete']:
                logger.warning(f"收到未知事件类型: {t}, data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            try:
                if t == 'error':
                    socketio_instance.emit('backtest_error', data, to=sid)
                    logger.error(f"后台回测错误: {data}")
                    return

                elif t == 'cancelled':
                    socketio_instance.emit('backtest_cancelled', data or {"message": "回测已取消"}, to=sid)
                    return

                elif t == 'backtest_start':
                    socketio_instance.emit('backtest_start', data, to=sid)

                elif t == 'progress':
                    socketio_instance.emit('progress', data, to=sid)

                elif t == 'initializing':
                    socketio_instance.emit('initializing', data, to=sid)

                elif t == 'initialized':
                    socketio_instance.emit('initialized', data, to=sid)

                elif t in ('daily_equity', 'daily_equity_engine'):
                    _emit_msgpack(socketio_instance, sid, 'daily_equity', data)

                elif t in ('new_trade', 'new_trade_engine'):
                    socketio_instance.emit('new_trade', data, to=sid)

                elif t == 'final_metrics':
                    _emit_msgpack(socketio_instance, sid, 'metrics_update', data, 
                                  fallback_func=_emit_large_data, log_size=True)

                elif t == 'risk_data':
                    _emit_msgpack(socketio_instance, sid, 'risk_update', data,
                                  fallback_func=_emit_large_data)

                elif t == 'stream_complete':
                    socketio_instance.emit('stream_complete', data or {"message": "回测完成"}, to=sid)
                    logger.info("后台线程回测完成")
                    return
            except Exception as emit_err:
                logger.warning(f"SocketIO 推送失败 (type={t}): {emit_err}")

    except Exception as e:
        logger.error(f"后台流式回测失败: {e}", exc_info=True)
        socketio_instance.emit('backtest_error', {"message": str(e)}, to=sid)
    finally:
        if active_backtests_dict is not None:
            active_backtests_dict.pop(sid, None)
