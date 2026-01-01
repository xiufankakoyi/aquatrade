"""
回测业务逻辑
包含后台回测任务和相关的工具函数
"""
import json
import gzip
import base64
from typing import Dict, Any, List, Callable, Optional
from threading import Event
from config.logger import get_logger
from utils.binary_packer import pack_backtest_result, estimate_size

logger = get_logger(__name__)


def _estimate_data_size(data: Any) -> int:
    """估算数据大小（字节）"""
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        return len(json_str.encode('utf-8'))
    except Exception:
        return 0


def _compress_data(data: Any) -> str:
    """
    压缩数据为base64字符串
    
    Args:
        data: 要压缩的数据（可JSON序列化）
    
    Returns:
        base64编码的压缩数据字符串
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        compressed = gzip.compress(json_str.encode('utf-8'), compresslevel=6)
        return base64.b64encode(compressed).decode('utf-8')
    except Exception as e:
        # 压缩失败时返回原始数据
        return json.dumps(data, ensure_ascii=False)


def _chunk_large_array(arr: List[Any], chunk_size: int = 1000) -> List[List[Any]]:
    """将大数组分块"""
    return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]


def _emit_large_data(socketio, sid: str, event_name: str, data: Dict[str, Any], logger_instance):
    """
    【修复】大数据传输优化：自动分块和压缩
    
    策略：
    1. 如果数据小于1MB，直接发送
    2. 如果数据大于1MB但小于10MB，压缩后发送
    3. 如果数据大于10MB，分块发送（每块最大5MB）
    
    Args:
        socketio: SocketIO实例
        sid: 会话ID
        event_name: 事件名称
        data: 要发送的数据
        logger_instance: 日志记录器
    """
    try:
        # 估算数据大小
        data_size = _estimate_data_size(data)
        size_mb = data_size / (1024 * 1024)
        
        # 阈值定义
        COMPRESS_THRESHOLD = 1 * 1024 * 1024  # 1MB
        CHUNK_THRESHOLD = 10 * 1024 * 1024  # 10MB
        MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per chunk
        
        if data_size < COMPRESS_THRESHOLD:
            # 小数据：直接发送
            socketio.emit(event_name, data, to=sid)
            logger_instance.debug(f"直接发送 {event_name} (大小: {size_mb:.2f}MB)")
        
        elif data_size < CHUNK_THRESHOLD:
            # 中等数据：压缩后发送
            try:
                compressed_data = _compress_data(data)
                socketio.emit(event_name, {
                    '_compressed': True,
                    '_data': compressed_data
                }, to=sid)
                logger_instance.info(f"压缩发送 {event_name} (原始: {size_mb:.2f}MB, 压缩后: {len(compressed_data)/1024/1024:.2f}MB)")
            except Exception as e:
                # 压缩失败，回退到直接发送
                logger_instance.warning(f"压缩失败，回退到直接发送: {e}")
                socketio.emit(event_name, data, to=sid)
        
        else:
            # 大数据：分块发送
            # 识别可能的大数组字段
            large_arrays = {}
            other_data = {}
            
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 100:
                    # 可能是大数组
                    large_arrays[key] = value
                else:
                    other_data[key] = value
            
            if not large_arrays:
                # 没有大数组，但整体很大，尝试压缩
                try:
                    compressed_data = _compress_data(data)
                    socketio.emit(event_name, {
                        '_compressed': True,
                        '_data': compressed_data
                    }, to=sid)
                    logger_instance.info(f"压缩发送 {event_name} (原始: {size_mb:.2f}MB)")
                except Exception:
                    # 压缩失败，直接发送（可能会失败，但至少尝试）
                    socketio.emit(event_name, data, to=sid)
                    logger_instance.warning(f"大数据直接发送 {event_name} (可能失败)")
            else:
                # 分块发送大数组
                total_chunks = 0
                for key, arr in large_arrays.items():
                    chunks = _chunk_large_array(arr, chunk_size=1000)  # 每块1000条
                    total_chunks += len(chunks)
                    
                    # 发送元数据
                    socketio.emit(event_name, {
                        '_chunked': True,
                        '_key': key,
                        '_total_chunks': len(chunks),
                        '_chunk_index': 0,
                        '_other_data': other_data,
                        '_data': chunks[0] if chunks else []
                    }, to=sid)
                    
                    # 发送后续块
                    for idx, chunk in enumerate(chunks[1:], start=1):
                        socketio.sleep(0.01)  # 避免阻塞
                        socketio.emit(event_name, {
                            '_chunked': True,
                            '_key': key,
                            '_total_chunks': len(chunks),
                            '_chunk_index': idx,
                            '_data': chunk
                        }, to=sid)
                
                logger_instance.info(f"分块发送 {event_name} (原始: {size_mb:.2f}MB, {total_chunks}块)")
    
    except Exception as e:
        logger_instance.error(f"发送大数据失败 {event_name}: {e}", exc_info=True)
        # 失败时尝试直接发送（作为最后手段）
        try:
            socketio.emit(event_name, data, to=sid)
        except Exception:
            logger_instance.error(f"直接发送也失败 {event_name}")


def run_backtest_background(
    socketio_instance,
    sid: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    benchmark_code: Optional[str],
    stop_event: Event,
    params: Optional[Dict[str, Any]] = None,
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
    # 延迟导入避免循环依赖
    if get_api_func is None:
        from server.app import get_api
        get_api_func = get_api
    
    logger.info(f"开始流式回测: {strategy_name} | 基准: {benchmark_code or 'None'}")

    try:
        # 调用 API 层的 stream_backtest（它会包含 daily_equity_engine -> daily_equity 等）
        for update in get_api_func().stream_backtest(
            strategy_name,
            start_date,
            end_date,
            benchmark_code,
            stop_event=stop_event,
            params=params,
        ):

            # 使用 socketio.sleep 让出控制权，避免阻塞（0.001 秒即可）
            socketio_instance.sleep(0.001)

            t = update.get('type')
            data = update.get('data', {})

            if stop_event.is_set():
                try:
                    socketio_instance.emit('backtest_cancelled', {"message": "回测已取消"}, to=sid)
                except Exception:
                    pass  # SocketIO 推送失败不影响主流程
                break

            # 【健壮性加固】所有 SocketIO 推送都包裹异常捕获
            # 【调试】记录所有收到的事件类型
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

                elif t == 'daily_equity':
                    # 映射为前端监听的 daily_update
                    # 使用 MsgPack 二进制打包（最优性能）
                    if isinstance(data, dict):
                        try:
                            # 使用优化的打包函数
                            packed = pack_backtest_result(data)
                            # 发送二进制数据（SocketIO 支持二进制）
                            socketio_instance.emit('daily_update', {
                                '_msgpack': True,
                                '_data': packed
                            }, to=sid)
                            # 【调试】只在每10天或第一天输出日志，避免日志过多
                            date_str = data.get('date', 'N/A')
                            if date_str != 'N/A':
                                # 提取日期中的天数部分，用于判断是否输出日志
                                try:
                                    day_num = int(date_str.split('-')[-1])
                                    if day_num % 10 == 0 or day_num == 1:
                                        logger.info(f"✓ 发送 daily_update (MsgPack: {len(packed)} bytes, date: {date_str})")
                                except:
                                    logger.info(f"✓ 发送 daily_update (MsgPack: {len(packed)} bytes, date: {date_str})")
                        except Exception as e:
                            logger.warning(f"MsgPack 打包失败，回退到 JSON: {e}")
                            socketio_instance.emit('daily_update', data, to=sid)
                            date_str = data.get('date', 'N/A')
                            logger.info(f"✓ 发送 daily_update (JSON, date: {date_str})")
                    else:
                        socketio_instance.emit('daily_update', data, to=sid)
                        logger.info(f"✓ 发送 daily_update (raw data)")

                elif t == 'new_trade':
                    # 交易数据通常较小，直接发送
                    socketio_instance.emit('new_trade', data, to=sid)

                elif t == 'final_metrics':
                    # 使用 MsgPack 二进制打包（替代 JSON + 压缩）
                    if isinstance(data, dict):
                        try:
                            packed = pack_backtest_result(data)
                            size_info = estimate_size(data)
                            logger.info(f"发送 metrics_update (MsgPack: {len(packed)} bytes, "
                                      f"压缩比: {size_info['compression_ratio']:.2%})")
                            socketio_instance.emit('metrics_update', {
                                '_msgpack': True,
                                '_data': packed
                            }, to=sid)
                        except Exception as e:
                            logger.warning(f"MsgPack 打包失败，回退到分块发送: {e}")
                            _emit_large_data(socketio_instance, sid, 'metrics_update', data, logger)
                    else:
                        _emit_large_data(socketio_instance, sid, 'metrics_update', data, logger)
                
                elif t == 'risk_data':
                    # 使用 MsgPack 二进制打包
                    if isinstance(data, dict):
                        try:
                            packed = pack_backtest_result(data)
                            socketio_instance.emit('risk_update', {
                                '_msgpack': True,
                                '_data': packed
                            }, to=sid)
                        except Exception as e:
                            logger.warning(f"MsgPack 打包失败，回退到分块发送: {e}")
                            _emit_large_data(socketio_instance, sid, 'risk_update', data, logger)
                    else:
                        _emit_large_data(socketio_instance, sid, 'risk_update', data, logger)

                elif t == 'stream_complete':
                    socketio_instance.emit('stream_complete', {"message": "回测完成"}, to=sid)
                    logger.info("后台线程回测完成")
                    return
            except Exception as emit_err:
                # SocketIO 推送失败不影响主流程，只记录日志
                logger.warning(f"SocketIO 推送失败 (type={t}): {emit_err}")

    except Exception as e:
        logger.error(f"后台流式回测失败: {e}", exc_info=True)
        socketio_instance.emit('backtest_error', {"message": str(e)}, to=sid)
    finally:
        # 清理活跃回测记录
        if active_backtests_dict is not None:
            active_backtests_dict.pop(sid, None)

