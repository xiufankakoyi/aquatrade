import os
import re
import sys
import threading
import time
import uuid
import math
import random
import warnings
import json
import gzip
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from threading import Event
from typing import Dict, Any, List
from urllib.parse import unquote
import pandas as pd
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
try:
    import duckdb  # type: ignore[import]
except Exception:  # noqa: BLE001
    duckdb = None

from visualization_api import BacktestVisualizationAPI
from profiles.profile_repository import (
    create_profile as create_strategy_profile,
    list_profiles as list_strategy_profiles,
    get_profile as get_strategy_profile,
)

# Define stopwords (including financial domain noise words)
STOPWORDS = {
    "就是", "今天", "昨天", "明天", "目前", "现在", "还是",
    "感觉", "觉得", "哈哈", "哈哈哈", "唉", "哎", "emm", "嘛", "嘿嘿", "呵呵",
    # Common Chinese stopwords
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "么", "得", "与", "为", "以", "对", "等", "当", "只", "而",
    "把", "被", "让", "向", "从", "将", "比", "及", "除", "关于", "由于", "因为",
    "所以", "如果", "但是", "不过", "虽然", "然而", "而且", "或者", "还是", "以及",
    "并且", "因此", "从而", "因而", "继而", "随后", "然后", "于是", "接着", "之后",
    "同时", "另外", "此外", "还有", "等等", "并", "且", "或", "者", "及", "如此",
    "这样", "那样", "这样一来", "如此一来"
}

# 公告和广告语模式（在分词前过滤）
ANNOUNCEMENT_PATTERNS = [
    r"关于.*?的公告",
    r"关于.*?预披露公告",
    r"关于.*?减持.*?公告",
    r"关于.*?承诺.*?公告",
    r".*?承诺.*?不减持.*?",
    r".*?股份减持计划.*?",
    r".*?控股股东.*?承诺.*?",
    r".*?董事.*?高级管理人员.*?",
    r".*?股份.*?减持.*?预披露",
    r".*?公告.*?公告",  # 重复"公告"的标题
]

# 广告语关键词（如果标题包含这些词，可能是广告）
AD_KEYWORDS = [
    "点击", "关注", "加微信", "扫码", "领取", "免费", "限时", "优惠", "促销",
    "立即", "马上", "赶快", "不要错过", "机会", "赚钱", "收益", "投资",
    "加群", "进群", "微信群", "QQ群", "联系", "咨询", "详情", "了解",
]

# 股市专业术语白名单（自定义词典）
STOCK_TERMS = [
    # 操作词
    "加仓", "建仓", "清仓", "做T", "做t", "抄底", "割肉", "满仓", "空仓",
    "减仓", "补仓", "平仓", "锁仓", "持仓", "开仓", "止盈", "止损",
    # 情绪词
    "诱多", "诱空", "洗盘", "踏空", "套牢", "起飞", "跳水", "杀跌", "追涨",
    "砸盘", "护盘", "拉盘", "出货", "吸筹", "震仓", "横盘", "破位",
    # 金融词
    "分红", "除权", "除息", "破净", "市盈率", "市净率", "主力", "北向资金", 
    "南向资金", "中字头", "蓝筹", "白马", "黑马", "题材", "概念", "板块",
    "涨停", "跌停", "涨停板", "跌停板", "一字板", "开板", "封板",
    "换手率", "成交量", "成交额", "流通股", "总股本", "市值", "估值",
    # 特定称呼
    "中行", "工行", "建行", "农行", "四大行", "银行股",
    # 技术分析词
    "均线", "MACD", "KDJ", "RSI", "布林线", "支撑位", "阻力位", "压力位",
    "金叉", "死叉", "顶背离", "底背离", "突破", "回踩", "反弹", "回调",
]

# 允许的词性标签（放宽限制，保留更多有意义的词）
# 包括：名词、动词、形容词、副词、数词、时间词等
ALLOWED_POS_FLAGS = ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'vd', 'a', 'ad', 'an', 'd', 'm', 't', 'f']

try:
    import jieba
    import jieba.posseg as pseg
    # 初始化 jieba 时加载自定义词典
    if jieba is not None:
        # 将股市术语添加到 jieba 词典
        for term in STOCK_TERMS:
            jieba.add_word(term, freq=1000, tag='n')  # 设置为高频词，确保不被拆分
except ImportError:
    jieba = None
    pseg = None

# CHANGED: 延迟初始化 API，在后台线程中预热数据库
api = None

def _normalize_strategy_id(strategy_name: str) -> str:
    """
    生成 URL 安全的策略 ID（仅用于兼容旧前端/日志），保留原始策略名备用
    """
    safe = ''.join(char.lower() if char.isalnum() else '_' for char in strategy_name)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe or strategy_name

def _init_api():
    """初始化 API 并预热数据库连接"""
    global api
    if api is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        logger.info("正在初始化数据库连接...")
        
        # 确保策略工厂被初始化
        from strategies.strategy_factory import StrategyFactory, get_factory
        factory = get_factory()
        strategies = factory.list_strategies()
        logger.info(f"策略工厂初始化完成，发现 {len(strategies)} 个策略")
        
        api = BacktestVisualizationAPI()
        # 执行一次简单的预热查询，让数据库连接和缓存就绪
        try:
            # CHANGED: 先确保 API 已初始化（懒加载模式）
            api._ensure_initialized()
            # 获取最近的交易日，触发数据库查询初始化
            dates = api.data_query.get_trading_dates()
            if dates:
                logger.info(f"数据库预热完成，最近交易日: {dates[-1] if dates else 'N/A'}")
            else:
                logger.warning("数据库预热完成，但未找到交易日数据")
        except Exception as e:
            logger.warning(f"数据库预热时出现警告: {e}", exc_info=True)

 # 在导入时立即初始化（同步初始化，确保 API 可用）
 # （已改为懒加载，由 before_first_request 钩子触发 _init_api）

# Redis 订阅线程（用于接收 Worker 进程的进度消息）
_redis_subscriber_thread = None
_redis_subscriber_running = False

def start_redis_subscriber():
    """
    启动 Redis 订阅线程，监听 Worker 进程发布的进度消息
    并将消息转发给前端（通过 socketio）
    """
    global _redis_subscriber_thread, _redis_subscriber_running
    
    if not REDIS_AVAILABLE:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.warning("Redis 不可用，跳过订阅线程启动")
        return
    
    if _redis_subscriber_thread is not None and _redis_subscriber_thread.is_alive():
        return  # 已经启动
    
    def redis_subscriber_worker():
        """Redis 订阅工作线程"""
        global _redis_subscriber_running
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        try:
            redis_sub = redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = redis_sub.pubsub()
            
            # 订阅所有通知频道（使用模式匹配）
            pubsub.psubscribe(f"{NOTIFICATION_CHANNEL_PREFIX}:*")
            
            logger.info(f"Redis 订阅线程启动，监听频道: {NOTIFICATION_CHANNEL_PREFIX}:*")
            _redis_subscriber_running = True
            
            while _redis_subscriber_running:
                try:
                    # 阻塞式接收消息，超时 1 秒
                    message = pubsub.get_message(timeout=1.0)
                    
                    if message is None:
                        continue
                    
                    # 消息类型：pmessage (pattern message)
                    if message['type'] == 'pmessage':
                        channel = message['channel']
                        data_str = message['data']
                        
                        try:
                            data = json.loads(data_str)
                            event = data.get('event')
                            event_data = data.get('data', {})
                            sid = data.get('sid')  # session ID
                            
                            # 通过 socketio 转发给前端
                            if sid:
                                socketio.emit(event, event_data, to=sid)
                            else:
                                socketio.emit(event, event_data)
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Redis 消息 JSON 解析失败: {e}")
                        except Exception as e:
                            logger.error(f"转发 Redis 消息失败: {e}", exc_info=True)
                            
                except redis.ConnectionError as e:
                    logger.error(f"Redis 订阅连接错误: {e}")
                    time.sleep(5)  # 等待后重试
                    try:
                        redis_sub = redis.from_url(REDIS_URL, decode_responses=True)
                        pubsub = redis_sub.pubsub()
                        pubsub.psubscribe(f"{NOTIFICATION_CHANNEL_PREFIX}:*")
                    except Exception:
                        logger.error("Redis 重新连接失败")
                        break
                except Exception as e:
                    logger.error(f"Redis 订阅线程错误: {e}", exc_info=True)
                    time.sleep(1)
            
            # 清理资源
            try:
                pubsub.close()
                redis_sub.close()
            except Exception:
                pass
            
            logger.info("Redis 订阅线程已停止")
            
        except Exception as e:
            logger.error(f"Redis 订阅线程启动失败: {e}", exc_info=True)
            _redis_subscriber_running = False
    
    _redis_subscriber_thread = threading.Thread(target=redis_subscriber_worker, daemon=True)
    _redis_subscriber_thread.start()
    
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Redis 订阅线程已启动")

app = Flask(__name__, static_folder='static')

CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "headers": ["Content-Type", "Authorization", "X-Requested-With"]}})
# 关键：开启 async_handlers，方便长任务
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    async_handlers=True,
                    logger=False,  # 关闭日志记录，减少输出
                    engineio_logger=False,  # 关闭引擎IO日志
                    ping_interval=25000,  # 增加ping间隔
                    ping_timeout=60000)  # 增加ping超时
active_backtests: Dict[str, Event] = {}
_restart_lock = threading.Lock()
_restart_scheduled = False

 # GA 任务管理
ga_tasks: Dict[str, Dict] = {}  # 内存任务表，用于存储异步GA优化任务
active_optimizations: Dict[str, Event] = {}  # 用于存储活跃的优化任务及其停止事件

# 【健壮性加固】全局数据查询实例（统一数据访问入口）
_global_data_query = None

def get_global_data_query():
    """获取全局数据查询实例（单例模式）"""
    global _global_data_query
    if _global_data_query is None:
        from database.optimized_data_query import OptimizedStockDataQuery
        _global_data_query = OptimizedStockDataQuery(warmup=True)
    return _global_data_query

# Redis 配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TASK_QUEUE = "aqua_tasks"  # Redis List 名称
NOTIFICATION_CHANNEL_PREFIX = "aqua_notifications"

# Redis 客户端（用于推送任务）
_redis_client = None

def get_redis_client():
    """获取 Redis 客户端（单例模式）"""
    global _redis_client
    if _redis_client is None and REDIS_AVAILABLE:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.info(f"Redis 客户端初始化成功: {REDIS_URL}")
        except Exception as e:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Redis 客户端初始化失败: {e}")
    return _redis_client

# 【健壮性加固】全局错误处理器
@app.errorhandler(Exception)
def handle_exception(e):
    """捕获所有未处理的异常，返回标准 JSON 格式"""
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    # CHANGED: 特别处理连接中止错误，这是常见的网络问题，不应该被视为严重错误
    if isinstance(e, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
        # 客户端在服务器发送响应之前关闭了连接，这是正常的网络行为
        # 只记录警告，不记录错误堆栈
        logger.debug(f"客户端连接已关闭: {type(e).__name__} - {str(e)}")
        # 返回 None 让 Flask 正常处理（实际上连接已关闭，无法返回响应）
        return None
    
    # CHANGED: 特别处理 404 错误，这是正常的 HTTP 状态码，不应该被视为错误
    from werkzeug.exceptions import NotFound, MethodNotAllowed
    if isinstance(e, NotFound):
        # 404 是正常的 HTTP 状态码，只记录 DEBUG 级别
        logger.debug(f"404 Not Found: {request.path}")
        return jsonify({
            'success': False,
            'error': '资源未找到',
            'data': []
        }), 404
    
    if isinstance(e, MethodNotAllowed):
        # 405 也是正常的 HTTP 状态码
        logger.debug(f"405 Method Not Allowed: {request.method} {request.path}")
        return jsonify({
            'success': False,
            'error': '请求方法不允许',
            'data': []
        }), 405
    
    # 记录错误堆栈
    import traceback
    error_trace = traceback.format_exc()
    logger.error(f"未处理的异常: {e}\n{error_trace}")
    
    # 返回标准 JSON 格式，确保前端能优雅降级
    return jsonify({
        'success': False,
        'error': str(e),
        'data': []
    }), 500

@app.errorhandler(500)
def handle_500(e):
    """专门处理 500 错误"""
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    # CHANGED: 特别处理连接中止错误
    if isinstance(e, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
        logger.debug(f"客户端连接已关闭 (500): {type(e).__name__} - {str(e)}")
        return None
    
    import traceback
    error_trace = traceback.format_exc()
    logger.error(f"500 错误: {e}\n{error_trace}")
    
    return jsonify({
        'success': False,
        'error': '服务器内部错误',
        'data': []
    }), 500

# CHANGED: 添加 after_request 钩子，捕获响应写入时的连接错误
@app.after_request
def after_request_handler(response):
    """在响应发送后处理，捕获连接错误"""
    try:
        return response
    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
        # 客户端在响应发送过程中关闭了连接，这是正常的网络行为
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.debug(f"响应发送时客户端连接已关闭: {type(e).__name__} - {str(e)}")
        # 返回原始响应，让 Flask 正常处理
        return response
    except Exception as e:
        # 其他异常正常处理
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.warning(f"after_request 钩子异常: {e}")
        return response

def _ensure_api_initialized() -> None:
    _init_api()

def _sanitize_json_data(data):
    """
    【健壮性加固】清洗数据，将 NaN/Infinity 转换为 null，防止 JSON 序列化报错
    """
    import math
    import numpy as np
    
    if isinstance(data, dict):
        return {k: _sanitize_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_json_data(item) for item in data]
    elif isinstance(data, (float, np.floating)):
        if math.isnan(data) or math.isinf(data):
            return None
        return float(data)
    elif isinstance(data, (int, np.integer)):
        return int(data)
    elif pd.isna(data):
        return None
    else:
        return data


def _schedule_restart(delay: float = 1.0) -> None:
    """
    在单独的线程里延迟执行 os.execl，实现平滑重启。
    """
    global _restart_scheduled
    with _restart_lock:
        if _restart_scheduled:
            return
        _restart_scheduled = True

    def _restart():
        time.sleep(delay)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    threading.Thread(target=_restart, daemon=True).start()

# ---------------- REST API ---------------- #

@app.route('/')
def index():
    """根路径路由"""
    # 移除 DEBUG 日志
    response = jsonify({"success": True, "message": "服务器正在运行"})
    response.headers.add('Content-Type', 'application/json')
    return response


@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """获取策略列表"""
    try:
        from strategies.strategy_factory import get_factory
        factory = get_factory()
        strategies = factory.list_strategies()

        result = []
        for i, strategy in enumerate(strategies):
            raw_name = strategy.get('name', '')
            safe_id = _normalize_strategy_id(raw_name)
            strategy_id = strategy.get('id') or raw_name or safe_id or f"strategy_{i}"

            # 检查重复，如果已存在则添加索引后缀
            if len([s for s in result if s['id'] == strategy_id]) > 0:
                strategy_id = f"{strategy_id}_{i}"

            result.append({
                "id": strategy_id,          # 策略 ID，用于前端识别
                "name": raw_name or strategy_id,
                "safeId": safe_id           # 安全的 URL 兼容 ID
            })

        response = jsonify({"success": True, "data": result})
        response.headers.add('Content-Type', 'application/json')
        return response
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取策略列表失败: {e}", exc_info=True)
        response = jsonify({"success": False, "data": [], "error": str(e)})
        response.headers.add('Content-Type', 'application/json')
        return response, 500

@app.route('/api/test_strategies', methods=['GET'])
def test_get_strategies():
    """测试用策略列表端点 - 完全独立实现"""
    try:
        # 移除 DEBUG 日志
        
        # 硬编码策略列表
        test_strategies = [
            {"id": "test_strategy_1", "name": "测试策略1", "description": "这是第一个测试策略"},
            {"id": "test_strategy_2", "name": "测试策略2", "description": "这是第二个测试策略"}
        ]
        
        # 直接返回测试数据
        response = jsonify({"success": True, "data": test_strategies})
        # 移除 DEBUG 日志
        return response
    except Exception as e:
        print(f"[ERROR] 测试端点失败: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/strategies/<strategy_id>/params', methods=['GET'])
def get_strategy_params(strategy_id: str):
    """获取指定策略的可优化参数列表"""
    try:
        # 允许同时使用原始名称和 safeId 进行访问
        resolved_id = unquote(strategy_id)
        try:
            params = api.get_strategy_params(resolved_id)
        except Exception:
            # 尝试使用 safeId 匹配原始策略名
            from strategies.strategy_factory import get_factory
            factory = get_factory()
            for item in factory.list_strategies():
                raw_name = item.get('name', '')
                if _normalize_strategy_id(raw_name) == resolved_id:
                    resolved_id = raw_name
                    break
            params = api.get_strategy_params(resolved_id)
        return jsonify(params)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run_backtest', methods=['POST'])
def run_backtest():
    """非流式备选接口"""
    try:
        data = request.get_json() or {}
        strategy_name = data.get('strategy_name')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        profile_id = data.get('profile_id')
        override_params = data.get('override_params') or {}

        # 如果提供了 profile_id，则从 DuckDB 中加载对应的参数预设
        if profile_id is not None:
            from profiles.profile_repository import get_profile as load_profile

            profile = load_profile(int(profile_id))
            if profile is None:
                return jsonify({"success": False, "error": f"Profile {profile_id} 不存在"}), 400
            # 合并 profile 参数和本次请求的覆盖参数
            params_from_profile = profile.get("params") or {}
            if not isinstance(params_from_profile, dict):
                params_from_profile = {}
            if not isinstance(override_params, dict):
                override_params = {}
            effective_params = {**params_from_profile, **override_params}
        else:
            # 不使用 Profile，直接使用请求体中的参数
            effective_params = data.get('params') or {}

        result = api.run_backtest_and_get_data(
            strategy_name,
            start_date,
            end_date,
            params=effective_params,
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/direct_test', methods=['GET'])
def direct_test():
    """全新的、完全独立的测试端点，用于调试路由和响应处理"""
    # 这个端点不使用任何外部依赖，直接返回硬编码数据
    test_data = {"success": True, "data": [{"id": "test1", "name": "测试数据1"}]}
    # 移除 DEBUG 日志
    return jsonify(test_data)

@app.route('/api/restart-backend', methods=['POST'])
def restart_backend():
    """
    触发后端自我重启：立即给前端成功响应，再在后台调用 os.execl 重新拉起进程。
    """
    _schedule_restart()
    return jsonify({"success": True, "message": "后端正在重启，请稍候 1-2 秒"}), 202

@app.route('/api/kline', methods=['GET'])
def get_kline_data():
    """
    HTTP 接口：返回指定标的在时间区间内的 K 线数据
    """
    symbol_code = request.args.get('symbol')
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if not symbol_code:
        return jsonify({"success": False, "error": "缺少 symbol 参数"}), 400

    try:
        history = api.get_symbol_kline(symbol_code, start_date, end_date)
        return jsonify(history)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/latest_price', methods=['GET'])
def get_latest_price():
    """
    返回一个或多个标的的最新价格
    """
    symbol = request.args.get('symbol')
    symbols_param = request.args.get('symbols')
    target_date = request.args.get('date')

    symbol_list = []
    if symbols_param:
        symbol_list = [code.strip() for code in symbols_param.split(',') if code.strip()]
    elif symbol:
        symbol_list = [symbol.strip()]

    if not symbol_list:
        return jsonify({"success": False, "error": "缺少 symbol/symbols 参数"}), 400

    try:
        latest_prices = api.get_latest_prices(symbol_list, target_date)
        return jsonify(latest_prices)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stock_sentiment', methods=['GET'])
def get_stock_sentiment():
    """基于股吧爬虫数据的股票舆情汇总，优先使用 Parquet+DuckDB，加速查询。"""
    try:
        base_dir = Path(__file__).parent

        limit_param = request.args.get('limit')
        try:
            limit = int(limit_param) if limit_param is not None else 50
        except (TypeError, ValueError):
            limit = 50

        # 1. 优先尝试使用 Parquet + DuckDB（由 scripts/build_guba_posts_parquet.py 预生成）
        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        if duckdb is not None and parquet_path.exists():
            try:
                parquet_str = str(parquet_path).replace('\\', '/')
                # DuckDB 直接在 Parquet 上聚合，避免逐文件读取 CSV
                # 优化：使用 TRY_CAST 但减少重复转换，添加 WHERE 过滤提高性能
                sql = f'''
                    SELECT
                        symbol,
                        COALESCE(CAST(stockbar_code AS VARCHAR), CAST(RIGHT(symbol, 6) AS VARCHAR)) AS stockCode,
                        COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName,
                        COUNT(*) AS totalPosts,
                        SUM(COALESCE(TRY_CAST(post_click_count AS BIGINT), 0)) AS totalClicks,
                        SUM(COALESCE(TRY_CAST(post_comment_count AS BIGINT), 0)) AS totalComments,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS bullishCount,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) < 0 THEN 1 ELSE 0 END) AS bearishCount,
                        SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) = 0 OR bullish_bearish IS NULL THEN 1 ELSE 0 END) AS neutralCount,
                        COALESCE(AVG(TRY_CAST(bullish_bearish AS DOUBLE)), 0.0) AS sentimentScore,
                        MAX(TRY_CAST(post_publish_time AS TIMESTAMP)) AS lastPostTime,
                        COUNT(DISTINCT CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE)) AS activeDays
                    FROM read_parquet('{parquet_str}')
                    WHERE symbol IS NOT NULL
                    GROUP BY symbol, stockbar_code, stockbar_name
                    ORDER BY totalComments DESC, totalPosts DESC
                    LIMIT ?
                '''

                effective_limit = limit if limit and limit > 0 else 1000
                con = duckdb.connect()
                try:
                    # 设置 DuckDB 性能参数以加速查询
                    try:
                        con.execute("SET threads TO 4")
                    except Exception:
                        pass  # 如果设置失败，使用默认值
                    try:
                        con.execute("SET memory_limit='2GB'")
                    except Exception:
                        pass
                    df = con.execute(sql, [effective_limit]).df()
                finally:
                    con.close()

                # 转换为前端期望的字段格式
                results = []
                for _, row in df.iterrows():
                    last_ts = row.get('lastPostTime')
                    if pd.isna(last_ts):
                        last_str = None
                    else:
                        # DuckDB 返回 Timestamp 时直接格式化为字符串
                        last_str = str(last_ts)

                    active_days = row.get('activeDays')
                    try:
                        active_days_int = int(active_days) if active_days is not None else None
                    except (TypeError, ValueError):
                        active_days_int = None

                    results.append({
                        "symbol": row.get('symbol') or '',
                        "stockCode": row.get('stockCode') or '',
                        "stockName": row.get('stockName') or '',
                        "totalPosts": int(row.get('totalPosts') or 0),
                        "totalClicks": int(row.get('totalClicks') or 0),
                        "totalComments": int(row.get('totalComments') or 0),
                        "bullishCount": int(row.get('bullishCount') or 0),
                        "bearishCount": int(row.get('bearishCount') or 0),
                        "neutralCount": int(row.get('neutralCount') or 0),
                        "sentimentScore": float(row.get('sentimentScore') or 0.0),
                        "lastPostTime": last_str,
                        "activeDays": active_days_int,
                    })

                return jsonify({"success": True, "data": results})
            except Exception:
                # DuckDB / Parquet 出错则回退到原始 CSV 方案
                pass

        # 2. 回退：沿用原来的逐 CSV 读取逻辑，保证兼容性
        data_dir = base_dir / 'spider' / 'data'
        if not data_dir.exists():
            return jsonify({"success": True, "data": []})

        results = []

        for csv_path in sorted(data_dir.glob('*_posts.csv')):
            symbol_code = csv_path.stem.replace('_posts', '')

            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
            except Exception:
                continue

            if df is None or df.empty:
                continue

            total_posts = int(len(df))

            if 'post_click_count' in df.columns:
                total_clicks = int(pd.to_numeric(df['post_click_count'], errors='coerce').fillna(0).sum())
            else:
                total_clicks = 0

            if 'post_comment_count' in df.columns:
                total_comments = int(pd.to_numeric(df['post_comment_count'], errors='coerce').fillna(0).sum())
            else:
                total_comments = 0

            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            sentiment_score = 0.0
            if 'bullish_bearish' in df.columns:
                bb = pd.to_numeric(df['bullish_bearish'], errors='coerce').fillna(0)
                bullish_count = int((bb > 0).sum())
                bearish_count = int((bb < 0).sum())
                neutral_count = int((bb == 0).sum())
                sentiment_score = float(bb.mean()) if len(bb) > 0 else 0.0

            stock_code = None
            stock_name = None
            if 'stockbar_code' in df.columns:
                try:
                    stock_code = str(df['stockbar_code'].iloc[0])
                except Exception:
                    stock_code = None
            if 'stockbar_name' in df.columns:
                try:
                    stock_name = str(df['stockbar_name'].iloc[0])
                except Exception:
                    stock_name = None

            last_post_time = None
            active_days = None
            if 'post_publish_time' in df.columns:
                try:
                    # 抑制日期解析格式警告
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=UserWarning, message='.*Could not infer format.*')
                        # 使用 format='mixed' 允许混合格式，提高解析性能并避免警告
                        # 如果 pandas 版本不支持，会回退到自动推断
                        try:
                            times = pd.to_datetime(
                                df['post_publish_time'],
                                format='mixed',
                                errors='coerce'
                            )
                        except (ValueError, TypeError):
                            # 回退到自动推断（兼容旧版本 pandas）
                            times = pd.to_datetime(
                                df['post_publish_time'],
                                errors='coerce'
                            )
                    if not times.isna().all():
                        last = times.max()
                        last_post_time = last.isoformat(sep=' ', timespec='seconds')
                        active_days = int(times.dt.date.nunique())
                except Exception:
                    # 兜底：解析异常时直接忽略时间信息，避免阻塞接口
                    last_post_time = None
                    active_days = None

            results.append({
                "symbol": symbol_code,
                "stockCode": stock_code or symbol_code[-6:],
                "stockName": stock_name or "",
                "totalPosts": total_posts,
                "totalClicks": total_clicks,
                "totalComments": total_comments,
                "bullishCount": bullish_count,
                "bearishCount": bearish_count,
                "neutralCount": neutral_count,
                "sentimentScore": sentiment_score,
                "lastPostTime": last_post_time,
                "activeDays": active_days,
            })

        results.sort(key=lambda x: (x['totalComments'], x['totalPosts']), reverse=True)
        if limit > 0:
            results = results[:limit]

        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": []}), 500


@app.route('/api/stock_sentiment_words', methods=['GET'])
def get_stock_sentiment_words():
    """返回单只股票用于词云的关键词和情绪权重。"""
    try:
        base_dir = Path(__file__).parent

        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"success": False, "error": "缺少 symbol 参数"}), 400

        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        df = None

        # 优先从 Parquet + DuckDB 读取该股票的帖子
        if duckdb is not None and parquet_path.exists():
            try:
                parquet_str = str(parquet_path).replace('\\', '/')
                sql = f"""
                    SELECT
                        symbol,
                        stockbar_code,
                        stockbar_name,
                        post_title,
                        post_click_count,
                        post_comment_count,
                        post_forward_count,
                        post_publish_time,
                        TRY_CAST(bullish_bearish AS DOUBLE) AS bullish_bearish
                    FROM read_parquet('{parquet_str}')
                    WHERE symbol = ?
                """
                con = duckdb.connect()
                try:
                    df = con.execute(sql, [symbol]).df()
                finally:
                    con.close()
            except Exception:
                df = None

        # 回退：直接读取 spider/data/{symbol}_posts.csv
        if df is None:
            csv_path = base_dir / 'spider' / 'data' / f'{symbol}_posts.csv'
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path, encoding='utf-8-sig')
                    df = df.copy()
                    df['symbol'] = symbol
                except Exception:
                    df = None

        if df is None or df.empty:
            return jsonify({"success": True, "data": {
                "symbol": symbol,
                "stockCode": symbol[-6:],
                "stockName": "",
                "totalPosts": 0,
                "totalClicks": 0,
                "totalComments": 0,
                "overallSentiment": None,
                "words": [],
            }})

        # 规范化数值列
        for col in ("post_click_count", "post_comment_count", "post_forward_count"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

        total_posts = int(len(df))
        total_clicks = int(df["post_click_count"].sum())
        total_comments = int(df["post_comment_count"].sum())

        # 情绪与分词库（若不可用则降级）
        try:
            from snownlp import SnowNLP  # type: ignore[import]
            import jieba  # type: ignore[import]
            import jieba.posseg as pseg  # type: ignore[import]
            
            # 确保自定义词典已加载
            if jieba is not None:
                for term in STOCK_TERMS:
                    jieba.add_word(term, freq=1000, tag='n')

            sentiment_available = True
        except Exception:
            SnowNLP = None  # type: ignore[assignment]
            jieba = None  # type: ignore[assignment]
            pseg = None  # type: ignore[assignment]
            sentiment_available = False

        import math

        word_stats: Dict[str, Dict[str, float]] = {}
        total_sentiment = 0.0
        sentiment_weight_sum = 0.0

        def tokenize(text: str):
            """
            改进的分词函数，确保细粒度分词，避免出现完整句子
            1. 使用精确模式分词，避免长词
            2. 对分词结果进行二次切分，确保词长度合理
            3. 只保留2-4个字的词（避免5-6字的短语被当作一个词）
            """
            if not text:
                return []
            
            words = []
            
            # 优先使用 jieba 精确模式分词（cut_all=False）
            if sentiment_available and jieba is not None:
                try:
                    # 使用精确模式，避免过度合并
                    seg_list = jieba.cut(text, cut_all=False)
                    
                    for word in seg_list:
                        word = word.strip()
                        if not word or word.isspace():
                            continue
                        
                        word_len = len(word)
                        
                        # 只保留2-4个字的词（避免出现长短语）
                        if word_len < 2 or word_len > 4:
                            # 如果词太长（>4），尝试进一步切分
                            if word_len > 4:
                                # 对长词进行二次切分
                                sub_words = jieba.cut(word, cut_all=False)
                                for sub_word in sub_words:
                                    sub_word = sub_word.strip()
                                    sub_len = len(sub_word)
                                    if 2 <= sub_len <= 4 and sub_word not in STOPWORDS:
                                        words.append(sub_word)
                            continue
                        
                        # 过滤停用词
                        if word in STOPWORDS:
                            continue
                        
                        # 过滤纯数字
                        if word.isdigit():
                            continue
                        
                        words.append(word)
                except Exception:
                    # 如果分词失败，使用简单切分
                    words = [w.strip() for w in re.findall(r"[\u4e00-\u9fff]{2,4}", text)
                            if w.strip() and w.strip() not in STOPWORDS and not w.strip().isdigit()]
            else:
                # 简单回退：按中文连续字符切分，只保留2-4个字
                words = [w.strip() for w in re.findall(r"[\u4e00-\u9fff]{2,4}", text)
                        if w.strip() and w.strip() not in STOPWORDS and not w.strip().isdigit()]
            
            # 去重但保持顺序
            seen = set()
            unique_words = []
            for w in words:
                if w not in seen:
                    seen.add(w)
                    unique_words.append(w)
            
            return unique_words

        def should_filter_title(title: str) -> bool:
            """在分词前过滤长句子和广告语"""
            if not title:
                return True
            
            # 过滤过长的标题（超过35个字符，可能是公告或广告）
            if len(title) > 35:
                return True
            
            # 过滤包含公告模式的标题
            for pattern in ANNOUNCEMENT_PATTERNS:
                if re.search(pattern, title):
                    return True
            
            # 过滤包含广告关键词的标题
            for keyword in AD_KEYWORDS:
                if keyword in title:
                    return True
            
            # 过滤包含过多标点符号的标题（可能是格式化文本）
            punctuation_count = len(re.findall(r'[，。、；：！？]', title))
            if punctuation_count > 3:
                return True
            
            return False

        for _, row in df.iterrows():
            title = str(row.get("post_title") or "").strip()
            if not title:
                continue
            
            # 在分词前过滤长句子和广告语
            if should_filter_title(title):
                continue

            clicks = float(row.get("post_click_count") or 0.0)
            comments = float(row.get("post_comment_count") or 0.0)
            forwards = float(row.get("post_forward_count") or 0.0)

            # 将帖子数、评论数、点击数综合为权重（对大数取 log 减少极端值影响）
            weight = 1.0 + math.log1p(clicks) + 2.0 * math.log1p(comments) + 1.5 * math.log1p(forwards)

            # 优先使用数据库中已计算好的 bullish_bearish 字段（与散点图保持一致）
            # 如果不存在，再使用 SnowNLP 实时计算
            score = None
            if 'bullish_bearish' in df.columns:
                try:
                    bb_value = row.get("bullish_bearish")
                    if bb_value is not None and pd.notna(bb_value):
                        # bullish_bearish 已经是 -1 到 1 之间的值，需要转换为 0-1 范围用于分类
                        # 但我们可以直接使用它来判断正负面
                        bb_float = float(bb_value)
                        if bb_float > 0:
                            # 正面：将 -1到1 映射到 0.5到1
                            score = 0.5 + (bb_float * 0.5)
                        elif bb_float < 0:
                            # 负面：将 -1到0 映射到 0到0.5
                            score = 0.5 + (bb_float * 0.5)
                        else:
                            # 中性
                            score = 0.5
                except (ValueError, TypeError):
                    score = None
            
            # 如果数据库中没有 bullish_bearish，回退到 SnowNLP
            if score is None and sentiment_available and SnowNLP is not None:
                try:
                    score = float(SnowNLP(title).sentiments)
                except Exception:
                    score = None

            if score is not None:
                total_sentiment += score * weight
                sentiment_weight_sum += weight

            # 改进情感分类阈值：使用更严格的阈值，提高区分度
            # 个股评论情感通常更极端，使用 0.55/0.45 作为阈值
            if score is None:
                label = "neutral"
            elif score >= 0.55:  # 从0.6降低到0.55，提高正面识别率
                label = "positive"
            elif score <= 0.45:  # 从0.4提高到0.45，提高负面识别率
                label = "negative"
            else:
                label = "neutral"

            # 分词处理（tokenize 内部已经处理了过滤）
            for token in tokenize(title):
                info = word_stats.setdefault(token, {
                    "weight": 0.0,
                    "positiveWeight": 0.0,
                    "negativeWeight": 0.0,
                    "count": 0.0,
                })
                info["weight"] += weight
                info["count"] += 1.0
                
                # 如果有 bullish_bearish 值，直接使用它来计算情绪权重
                # 这样可以更准确地反映情绪，与散点图保持一致
                if bb_value is not None and pd.notna(bb_value):
                    bb_float = float(bb_value)
                    if bb_float > 0:
                        info["positiveWeight"] += weight * bb_float  # 正面权重 = weight * 情绪强度
                    elif bb_float < 0:
                        info["negativeWeight"] += weight * abs(bb_float)  # 负面权重 = weight * |情绪强度|
                    # bb_float == 0 时，不累加正负面权重（保持为0，表示中性）
                else:
                    # 如果没有 bullish_bearish，使用 label 分类（回退方案）
                    if label == "positive":
                        info["positiveWeight"] += weight
                    elif label == "negative":
                        info["negativeWeight"] += weight

        words = []
        for token, info in word_stats.items():
            weight = float(info.get("weight", 0.0))
            positive_weight = float(info.get("positiveWeight", 0.0))
            negative_weight = float(info.get("negativeWeight", 0.0))
            count = int(info.get("count", 0.0))
            
            # 计算情绪倾向（-1 到 1，-1=完全负面，0=中性，1=完全正面）
            # 改进：使用更敏感的计算方式，提高区分度
            sentiment_score = 0.0
            if weight > 0:
                # 情绪得分 = (正面权重 - 负面权重) / 总权重
                sentiment_score = (positive_weight - negative_weight) / weight
                # 放大差异：如果正负面权重差异明显，增强信号
                if abs(sentiment_score) > 0.3:
                    # 对极端情绪进行放大（但不超过±1）
                    sentiment_score = sentiment_score * 1.2
                # 限制在 -1 到 1 之间
                sentiment_score = max(-1.0, min(1.0, sentiment_score))
            
            words.append({
                "word": token,
                "weight": weight,  # 词的总权重，用于控制词云中词的大小（weight 越大，词越大）
                "positiveWeight": positive_weight,  # 正面情绪权重
                "negativeWeight": negative_weight,  # 负面情绪权重
                "count": count,  # 词出现的次数
                "sentiment": sentiment_score,  # 情绪得分（-1到1），用于控制词的颜色
                # 前端使用建议：
                # - 词大小：根据 weight 值按比例缩放（weight 越大，字体越大）
                # - 词颜色：根据 sentiment 值设置颜色
                #   * sentiment > 0.2: 正面情绪，使用暖色（如绿色、橙色）
                #   * sentiment < -0.2: 负面情绪，使用冷色（如红色、蓝色）
                #   * -0.2 <= sentiment <= 0.2: 中性情绪，使用中性色（如灰色）
            })

        # 按权重排序，确保词大小与出现程度正相关（权重高的词排在前面）
        words.sort(key=lambda x: x["weight"], reverse=True)
        words = words[:150]

        if sentiment_weight_sum > 0:
            overall_sentiment = total_sentiment / sentiment_weight_sum
        else:
            overall_sentiment = None

        stock_code = str(df.get("stockbar_code").iloc[0]) if "stockbar_code" in df.columns and len(df) > 0 else symbol[-6:]
        stock_name = str(df.get("stockbar_name").iloc[0]) if "stockbar_name" in df.columns and len(df) > 0 else ""

        return jsonify({
            "success": True,
            "data": {
                "symbol": symbol,
                "stockCode": stock_code,
                "stockName": stock_name,
                "totalPosts": total_posts,
                "totalClicks": total_clicks,
                "totalComments": total_comments,
                "overallSentiment": overall_sentiment,
                "words": words,
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "data": None}), 500


@app.route('/api/stock_sentiment_timeline', methods=['GET'])
def get_stock_sentiment_timeline():
    """获取个股多空博弈时间序列数据（按时间分组，显示看多、看空、中立三条线）"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({"success": False, "error": "缺少 symbol 参数", "data": []}), 400
        
        base_dir = Path(__file__).parent
        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        
        if duckdb is None or not parquet_path.exists():
            return jsonify({"success": False, "error": "Parquet 数据文件不存在", "data": []}), 500
        
        parquet_str = str(parquet_path).replace('\\', '/')
        
        # 提取6位数字代码
        if symbol.startswith('sz') or symbol.startswith('sh'):
            code_6 = symbol[2:] if len(symbol) > 2 else symbol
            full_symbol = symbol
        else:
            code_6 = symbol[-6:] if len(symbol) >= 6 else symbol.zfill(6)
            full_symbol = symbol
        
        # 构建多种匹配条件
        symbol_conditions = [
            f"symbol = '{full_symbol}'",
            f"symbol = '{code_6}'",
            f"RIGHT(symbol, 6) = '{code_6}'",
            f"stockbar_code = '{code_6}'",
            f"symbol LIKE '%{code_6}%'"
        ]
        where_clause = ' OR '.join(symbol_conditions)
        
        # 按时间分组（按小时），统计看多、看空、中立的数量
        sql = f"""
            SELECT
                DATE_TRUNC('hour', TRY_CAST(post_publish_time AS TIMESTAMP)) AS time_hour,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS bullishCount,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) < 0 THEN 1 ELSE 0 END) AS bearishCount,
                SUM(CASE WHEN TRY_CAST(bullish_bearish AS DOUBLE) = 0 OR bullish_bearish IS NULL THEN 1 ELSE 0 END) AS neutralCount,
                COUNT(*) AS totalCount,
                COALESCE(CAST(stockbar_name AS VARCHAR), '') AS stockName
            FROM read_parquet('{parquet_str}')
            WHERE ({where_clause})
                AND TRY_CAST(post_publish_time AS TIMESTAMP) IS NOT NULL
            GROUP BY time_hour, stockbar_name
            ORDER BY time_hour ASC
        """
        
        con = duckdb.connect()
        try:
            con.execute("SET threads TO 4")
            con.execute("SET memory_limit='2GB'")
            df = con.execute(sql).df()
        finally:
            con.close()
        
        if df.empty:
            return jsonify({"success": True, "data": [], "stockName": ""})
        
        # 获取股票名称（从第一条记录）
        stock_name = str(df.iloc[0].get('stockName', '')) if 'stockName' in df.columns else ''
        
        # 转换为前端需要的格式
        results = []
        for _, row in df.iterrows():
            time_hour = row.get('time_hour')
            if pd.isna(time_hour):
                continue
            
            # 格式化时间为字符串（如 "2024-01-01 09:00"）
            if isinstance(time_hour, pd.Timestamp):
                time_str = time_hour.strftime('%Y-%m-%d %H:%M')
            else:
                time_str = str(time_hour)
            
            results.append({
                'time': time_str,
                'bullishCount': int(row.get('bullishCount', 0)),
                'bearishCount': int(row.get('bearishCount', 0)),
                'neutralCount': int(row.get('neutralCount', 0)),
                'totalCount': int(row.get('totalCount', 0))
            })
        
        return jsonify({
            "success": True,
            "data": results,
            "stockName": stock_name
        })
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取个股多空博弈时间序列数据失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e), "data": []}), 500


@app.route('/api/strategies/<strategy_name>/profiles', methods=['GET'])
def api_list_strategy_profiles(strategy_name: str):
    """
    列出某个策略下的所有参数预设（Profile）。
    """
    try:
        # 允许前端使用 URL 编码后的名称
        resolved_name = unquote(strategy_name)
        profiles = list_strategy_profiles(resolved_name)
        return jsonify({"success": True, "data": profiles})
    except Exception as e:
        print(f"[ERROR] 获取策略预设列表失败: {e}")
        return jsonify({"success": False, "error": str(e), "data": []}), 500


@app.route('/api/strategies/<strategy_name>/profiles', methods=['POST'])
def api_create_strategy_profile(strategy_name: str):
    """
    为指定策略创建一个新的参数预设。
    """
    try:
        from strategies.strategy_factory import get_factory

        data = request.get_json() or {}
        profile_name = data.get("profile_name")
        description = data.get("description")
        params = data.get("params") or {}
        source = data.get("source", "optimization")

        if not profile_name:
            return jsonify({"success": False, "error": "profile_name 不能为空"}), 400
        if not isinstance(params, dict):
            return jsonify({"success": False, "error": "params 必须是对象"}), 400

        # 校验策略是否存在
        factory = get_factory()
        available = {s.get("name") for s in factory.list_strategies()}
        resolved_name = unquote(strategy_name)
        if resolved_name not in available:
            return jsonify({"success": False, "error": f"策略 {resolved_name} 不存在"}), 400

        profile = create_strategy_profile(
            strategy_name=resolved_name,
            profile_name=profile_name,
            description=description,
            params_dict=params,
            source=source,
        )
        return jsonify({"success": True, "data": profile}), 201
    except Exception as e:
        print(f"[ERROR] 创建策略预设失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/strategy-profiles/<int:profile_id>', methods=['GET'])
def api_get_strategy_profile(profile_id: int):
    """
    获取单个参数预设详情。
    """
    try:
        profile = get_strategy_profile(profile_id)
        if profile is None:
            return jsonify({"success": False, "error": "Profile 不存在"}), 404
        return jsonify({"success": True, "data": profile})
    except Exception as e:
        print(f"[ERROR] 获取策略预设详情失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/strategy/<version_id>', methods=['GET'])
def get_strategy_detail(version_id):
    """
    获取策略详情（包括回测结果）
    注意：由于系统使用流式回测，数据保存在前端的 sessionStorage 中
    此接口返回空数据结构，实际数据应该从前端的 backtestStore 获取
    """
    try:
        # 检查是否是有效的策略名称
        available_strategies = api.get_strategy_list()
        strategy_names = [s['id'] for s in available_strategies]
        
        if version_id in strategy_names:
            # 返回符合前端 BacktestResult 接口的空数据结构
            # 前端应该从 backtestStore 中获取实际的回测数据
            return jsonify({
                "versionId": version_id,
                "metrics": {
                    "totalReturn": 0,
                    "annualizedReturn": 0,
                    "maxDrawdown": 0,
                    "sharpeRatio": 0,
                    "winRate": 0,
                    "tradesCount": 0,
                    "profitFactor": 0,
                    "volatility": 0,
                    "sortinoRatio": 0,
                    "avgTradeReturn": 0,
                    "maxWinningStreak": 0,
                    "maxLosingStreak": 0
                },
                "equityCurve": [],
                "monthlyReturns": [],
                "trades": []  # 空数组，不是占位符
            })
        else:
            return jsonify({"error": f"策略版本 {version_id} 不存在"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Socket.IO 连接事件 ---------------- #

@socketio.on('connect')
def handle_connect():
    """【健壮性加固】SocketIO 连接事件，添加异常捕获"""
    try:
        # 只在 DEBUG 模式下输出连接信息
        debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
        if debug_mode:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Socket.IO 客户端已连接: {request.sid}")
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Socket.IO 连接处理失败: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """【健壮性加固】SocketIO 断开事件，添加异常捕获"""
    try:
        # 只在 DEBUG 模式下输出断开信息
        debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
        if debug_mode:
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Socket.IO 客户端已断开: {request.sid}")
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Socket.IO 断开处理失败: {e}")

# ---------------- 大数据传输优化工具函数 ---------------- #

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


def _emit_large_data(socketio, sid: str, event_name: str, data: Dict[str, Any], logger):
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
        logger: 日志记录器
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
            logger.debug(f"直接发送 {event_name} (大小: {size_mb:.2f}MB)")
        
        elif data_size < CHUNK_THRESHOLD:
            # 中等数据：压缩后发送
            try:
                compressed_data = _compress_data(data)
                socketio.emit(event_name, {
                    '_compressed': True,
                    '_data': compressed_data
                }, to=sid)
                logger.info(f"压缩发送 {event_name} (原始: {size_mb:.2f}MB, 压缩后: {len(compressed_data)/1024/1024:.2f}MB)")
            except Exception as e:
                # 压缩失败，回退到直接发送
                logger.warning(f"压缩失败，回退到直接发送: {e}")
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
                    logger.info(f"压缩发送 {event_name} (原始: {size_mb:.2f}MB)")
                except Exception:
                    # 压缩失败，直接发送（可能会失败，但至少尝试）
                    socketio.emit(event_name, data, to=sid)
                    logger.warning(f"大数据直接发送 {event_name} (可能失败)")
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
                
                logger.info(f"分块发送 {event_name} (原始: {size_mb:.2f}MB, {total_chunks}块)")
    
    except Exception as e:
        logger.error(f"发送大数据失败 {event_name}: {e}", exc_info=True)
        # 失败时尝试直接发送（作为最后手段）
        try:
            socketio.emit(event_name, data, to=sid)
        except Exception:
            logger.error(f"直接发送也失败 {event_name}")


# ---------------- 真正的后台回测任务（不要加装饰器！） ---------------- #

def run_backtest_background(sid, strategy_name, start_date, end_date, benchmark_code, stop_event: Event, params=None):
    """
    在后台线程/协程里跑流式回测，并不断通过 socketio.emit 推送给前端
    """
    # 使用 logger 记录重要信息（INFO 级别）
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info(f"开始流式回测: {strategy_name} | 基准: {benchmark_code or 'None'}")

    try:
        # 调用 API 层的 stream_backtest（它会包含 daily_equity_engine -> daily_equity 等）
        for update in api.stream_backtest(
            strategy_name,
            start_date,
            end_date,
            benchmark_code,
            stop_event=stop_event,
            params=params,
        ):

            # 使用 socketio.sleep 让出控制权，避免阻塞（0.001 秒即可）
            socketio.sleep(0.001)

            t = update.get('type')
            data = update.get('data', {})

            if stop_event.is_set():
                try:
                    socketio.emit('backtest_cancelled', {"message": "回测已取消"}, to=sid)
                except Exception:
                    pass  # SocketIO 推送失败不影响主流程
                break

            # 【健壮性加固】所有 SocketIO 推送都包裹异常捕获
            try:
                if t == 'error':
                    socketio.emit('backtest_error', data, to=sid)
                    logger.error(f"后台回测错误: {data}")
                    return

                elif t == 'cancelled':
                    socketio.emit('backtest_cancelled', data or {"message": "回测已取消"}, to=sid)
                    return

                elif t == 'backtest_start':
                    socketio.emit('backtest_start', data, to=sid)

                elif t == 'progress':
                    socketio.emit('progress', data, to=sid)

                elif t == 'initializing':
                    socketio.emit('initializing', data, to=sid)

                elif t == 'initialized':
                    socketio.emit('initialized', data, to=sid)

                elif t == 'daily_equity':
                    # 映射为前端监听的 daily_update
                    socketio.emit('daily_update', data, to=sid)

                elif t == 'new_trade':
                    socketio.emit('new_trade', data, to=sid)

                elif t == 'final_metrics':
                    # 【修复】大数据传输优化：分块和压缩
                    _emit_large_data(socketio, sid, 'metrics_update', data, logger)
                
                elif t == 'risk_data':
                    # 【修复】大数据传输优化：分块和压缩
                    _emit_large_data(socketio, sid, 'risk_update', data, logger)

                elif t == 'stream_complete':
                    socketio.emit('stream_complete', {"message": "回测完成"}, to=sid)
                    logger.info("后台线程回测完成")
                    return
            except Exception as emit_err:
                # SocketIO 推送失败不影响主流程，只记录日志
                logger.warning(f"SocketIO 推送失败 (type={t}): {emit_err}")

    except Exception as e:
        logger.error(f"后台流式回测失败: {e}", exc_info=True)
        socketio.emit('backtest_error', {"message": str(e)}, to=sid)
    finally:
        active_backtests.pop(sid, None)

# ---------------- 前端触发回测的事件处理handler ---------------- #

@socketio.on('run_streaming_backtest')
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
                from profiles.profile_repository import get_profile as load_profile

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

        # 当前这位前端用户�?sid
        sid = request.sid

        # 给前端一个“我收到了”的反馈（你 App.vue 有监听）
        emit('request_received', {"message": "回测请求已收到"})

        # 启动后台任务，不阻塞当前事件 handler
        stop_event = Event()
        active_backtests[sid] = stop_event

        socketio.start_background_task(
            run_backtest_background,
            sid, strategy_name, start_date, end_date, benchmark_code, stop_event, effective_params
        )

    except Exception as e:
        print("❌ 流式回测启动失败:", e)
        emit('backtest_error', {"message": str(e)})

# CHANGED: 将取消回测的处理函数移到模块级别，避免嵌套定义问题
@socketio.on('cancel_streaming_backtest')
def handle_cancel_backtest(data=None):
    """
    处理取消回测请求
    CHANGED: 接受 data 参数（即使不使用），避免 Socket.IO 参数不匹配错误
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)
    sid = request.sid
    stop_event = active_backtests.get(sid)
    if stop_event:
        stop_event.set()
        emit('backtest_cancel_ack', {"message": "正在停止回测..."})
        logger.info(f"收到取消回测请求，已设置停止标志 (sid: {sid})")
    else:
        emit('backtest_cancel_ack', {"message": "当前没有正在运行的回测"})
        logger.warning(f"收到取消回测请求，但当前没有运行的回测 (sid: {sid})")

@socketio.on('request_kline')
def handle_request_kline(data):
    symbol_code = data.get('symbol_code')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol_code:
        emit('kline_data', {"error": "缺少 symbol_code"}, to=request.sid)
        return

    print(f"📈 请求 K 线 {symbol_code} | {start_date} ~ {end_date}")
    history = api.get_symbol_kline(symbol_code, start_date, end_date)
    emit('kline_data', {
        "request_id": data.get('request_id'),
        "symbol_code": symbol_code,
        "symbolCode": symbol_code,
        "symbol_name": api.stock_info_map.get(symbol_code, symbol_code),
        "data": history
    }, to=request.sid)

# ---------------- 参数优化相关事件处理 ---------------- #

def push_optimization_task_to_redis(sid, config):
    """
    将优化任务推送到 Redis 队列
    
    Args:
        sid: Socket.IO session ID
        config: 优化配置
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    redis_client = get_redis_client()
    if not redis_client:
        logger.error("Redis 不可用，无法推送任务")
        return False
    
    try:
        task_data = {
            "sid": sid,
            "config": config
        }
        
        # 推送到 Redis List
        redis_client.rpush(TASK_QUEUE, json.dumps(task_data))
        logger.info(f"优化任务已推送到 Redis 队列 (sid: {sid})")
        return True
    except Exception as e:
        logger.error(f"推送任务到 Redis 失败: {e}", exc_info=True)
        return False

@socketio.on('stop_optimization')
def handle_stop_optimization(data):
    """处理停止优化请求"""
    from utils.logger import get_logger
    logger = get_logger(__name__)
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

@socketio.on('run_optimization')
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
            metric_map = {
                'sharpeRatio': 'sharpe',
                'totalReturn': 'returns',
                'maxDrawdown': 'sharpe',  # 回撤需要特殊处理
                'calmarRatio': 'calmar',
                'sortinoRatio': 'sortino'
            }
            target = metric_map.get(target_metric, target_metric.replace('_ratio', '').lower())
            
            # 根据算法类型构建 options
            options = {
                "target": target,
                "target_metric": target_metric,
                "mode": mode,
            }
            
            # 根据算法类型添加特定参数
            if method == 'ga':
                options.update({
                    "iterations": algo_params.get('generations', 100),
                    "generations": algo_params.get('generations', 100),
                    "population": algo_params.get('pop_size', 50),
                    "mutation_rate": algo_params.get('mutation_rate', 0.1),
                    "crossover_rate": algo_params.get('crossover_rate', 0.8),
                })
            elif method == 'pso':
                options.update({
                    "iterations": algo_params.get('iterations', 100),
                    "swarm_size": algo_params.get('particle_count', 30),
                    "w": algo_params.get('w', 0.7),
                    "c1": algo_params.get('c1', 1.5),
                    "c2": algo_params.get('c2', 1.5),
                })
            elif method == 'cma_es':
                options.update({
                    "iterations": algo_params.get('max_evaluations', 100),
                    "population": algo_params.get('population', 20),
                    "sigma": algo_params.get('sigma', 0.5),
                })
            elif method == 'cmaes':  # 兼容前端可能发送的 cmaes 格式
                options.update({
                    "iterations": algo_params.get('max_evaluations', 100),
                    "population": algo_params.get('population', 20),
                    "sigma": algo_params.get('sigma', 0.5),
                })
            elif method == 'sa':
                options.update({
                    "iterations": 1000,  # 模拟退火的迭代次数由温度控制
                    "initial_temp": algo_params.get('initial_temp', 100.0),
                    "min_temp": algo_params.get('min_temp', 0.01),
                    "cooling_rate": algo_params.get('cooling_rate', 0.95),
                    "steps_per_temp": algo_params.get('steps_per_temp', 10),
                })
            elif method == 'bayesian':
                options.update({
                    "iterations": algo_params.get('iterations', 50),
                    "init_points": algo_params.get('random_init_points', 10),
                    "acquisition_function": algo_params.get('acquisition_function', 'EI'),
                })
            elif method == 'grid':
                options.update({
                    "iterations": 1000,  # 网格搜索的迭代次数由参数组合数决定
                    "grid_density": algo_params.get('grid_density', 10),
                    "parallel": algo_params.get('parallel', True),
                })
            
            # 添加约束条件
            constraints = objective.get('constraints', {})
            if constraints:
                options['constraints'] = constraints
            
            # 添加验证框架配置
            if validation.get('enabled'):
                options['validation'] = validation

            # 三段区间：前端通过 backtest 传入，如果缺失则退回主回测区间
            train_start_date = backtest.get('train_start_date') or start_date
            train_end_date = backtest.get('train_end_date') or end_date
            val_start_date = backtest.get('val_start_date') or None
            val_end_date = backtest.get('val_end_date') or None
            test_start_date = backtest.get('test_start_date') or None
            test_end_date = backtest.get('test_end_date') or None

            print("📌 参数优化区间:")
            print(f"   train: {train_start_date} ~ {train_end_date}")
            print(f"   val  : {val_start_date} ~ {val_end_date}")
            print(f"   test : {test_start_date} ~ {test_end_date}")
            
            optimization_config = {
                "strategy_name": strategy_name,
                "start_date": start_date,
                "end_date": end_date,
                "method": method,
                "param_ranges": param_ranges,
                "options": options,
                "selected_params": [p['name'] for p in param_ranges],
                "mode": mode,
                "train_start_date": train_start_date,
                "train_end_date": train_end_date,
                "val_start_date": val_start_date,
                "val_end_date": val_end_date,
                "test_start_date": test_start_date,
                "test_end_date": test_end_date,
            }
            
        else:
            # 旧格式处理（向后兼容）
            strategy_name = data.get('strategy_name')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            config_data = data.get('config', {})
            selected_params = data.get('selected_params', {})
            
            if not all([strategy_name, start_date, end_date]):
                emit('optimization_error', {"message": "缺少必要参数: strategy_name, start_date, end_date"})
                return
            
            from utils.logger import get_logger
            logger = get_logger(__name__)
            debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
            if debug_mode:
                logger.debug(f"收到参数优化请求（旧格式）: {strategy_name} | {start_date}~{end_date}")
                logger.debug(f"   算法: {config_data.get('method', 'genetic')} | 迭代: {config_data.get('iterations', 50)}")
                logger.debug(f"   选中参数: {list(selected_params.keys())}")
            
            # 构建 param_ranges
            param_ranges = []
            for param_name, bounds in selected_params.items():
                if isinstance(bounds, list) and len(bounds) == 2:
                    lower, upper = float(bounds[0]), float(bounds[1])
                    
                    # 验证参数范围
                    if lower >= upper:
                        logger.warning(f"参数范围验证失败: {param_name} 范围 [{lower}, {upper}] 无效，将使用安全范围")
                        if lower > 1000:
                            lower, upper = 0, lower + 100
                        else:
                            lower, upper = min(lower, upper - 1), max(upper, lower + 1)
                    
                    # 判断参数类型
                    is_int_param = (
                        'days' in param_name or 
                        'candidates' in param_name or 
                        'stocks' in param_name or
                        (param_name.endswith('_ma') and 'ratio' not in param_name and 'threshold' not in param_name) or
                        param_name in ['market_cap_min', 'market_cap_max']
                    )
                    param_type = 'int' if is_int_param else 'float'
                    
                    param_ranges.append({
                        "name": param_name,
                        "bounds": [lower, upper],
                        "type": param_type
                    })
                    print(f"📊 参数范围设置: {param_name} = [{lower}, {upper}] ({param_type})")
            
            if not param_ranges:
                emit('optimization_error', {"message": "没有有效的参数范围定义"})
                return
            
            # 构建优化配置
            optimization_config = {
                "strategy_name": strategy_name,
                "start_date": start_date,
                "end_date": end_date,
                "method": config_data.get('method', 'genetic'),
                "param_ranges": param_ranges,
                "options": {
                    "target": config_data.get('target', 'sharpe'),
                    "iterations": config_data.get('iterations', 50),
                    "generations": config_data.get('iterations', 50),
                    "population": config_data.get('population', 20),
                    "mutation_rate": config_data.get('mutationRate', 0.1),
                    "crossover_rate": config_data.get('crossoverRate', 0.7),
                    "init_points": config_data.get('init_points', 5),
                },
                "selected_params": list(selected_params.keys()) if selected_params else None,
            }
        
        # 推送任务到 Redis 队列（异步架构）
        success = push_optimization_task_to_redis(sid, optimization_config)
        
        if success:
            emit('optimization_request_received', {"message": "优化请求已收到，已加入队列，等待 Worker 处理..."})
        else:
            emit('optimization_error', {"message": "Redis 不可用，无法启动优化任务"})
        
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"参数优化启动失败: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        emit('optimization_error', {"message": str(e)})

# ---------------- GA 优化异步任务处理 ---------------- #

def ga_worker(task_id: str, args: dict):
    """
    GA优化工作线程
    在后台执行GA优化并更新任务状态
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)
    ga_tasks[task_id]["status"] = "running"
    try:
        # 导入run_ga_optimization函数
        from tools.ga_optimize_strategy import run_ga_optimization
        
        # 执行GA优化
        result = run_ga_optimization(**args)
        
        # 更新任务状态和结果
        ga_tasks[task_id]["status"] = "finished"
        ga_tasks[task_id]["result"] = result
        logger.info(f"GA优化任务完成 (task_id: {task_id})")
        
    except Exception as e:
        # 捕获错误并更新任务状态
        ga_tasks[task_id]["status"] = "error"
        ga_tasks[task_id]["error"] = str(e)
        logger.error(f"GA优化任务失败 (task_id: {task_id}): {e}", exc_info=True)
        import traceback
        traceback.print_exc()


@app.route("/api/ga_optimize/start", methods=["POST"])
def api_ga_start():
    """
    开始GA优化任务
    返回task_id供前端轮询
    """
    data = request.get_json(force=True) or {}
    
    # 获取必要参数
    strategy_id = data.get("strategy_id", "聚宽量比市值策略V3_严格趋势")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    pop_size = int(data.get("pop_size", 20))
    generations = int(data.get("generations", 20))
    
    # 参数验证
    if not start_date or not end_date:
        return jsonify({"error": "start_date / end_date 必填"}), 400
    
    # 生成任务ID并初始化任务
    task_id = str(uuid.uuid4())
    ga_tasks[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
    }
    
    # 构建GA优化参数
    args = dict(
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        pop_size=pop_size,
        generations=generations,
        db_path=None,
        keys=None  # 使用全部参数进行优化
    )
    
    # 启动后台线程执行GA优化
    t = threading.Thread(target=ga_worker, args=(task_id, args), daemon=True)
    t.start()
    
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info(f"启动GA优化任务 (task_id: {task_id}, strategy: {strategy_id})")
    
    # 返回任务ID给前端
    return jsonify({"ok": True, "task_id": task_id})


@app.route("/api/ga_optimize/status/<task_id>", methods=["GET"])
def api_ga_status(task_id: str):
    """
    查询GA优化任务状态
    """
    # 查找任务
    task = ga_tasks.get(task_id)
    if not task:
        return jsonify({"error": "unknown task_id"}), 404
    
    # 返回任务状态
    return jsonify(task)

# ========== 高级情感分析API路由 ==========
@app.route('/api/sentiment_trends', methods=['GET'])
def get_sentiment_trends():
    """获取情感趋势数据（从真实数据库查询）"""
    try:
        symbol = request.args.get('symbol')
        days = int(request.args.get('days', 7))
        
        base_dir = Path(__file__).parent
        parquet_path = base_dir / 'parquet_data' / 'guba_posts.parquet'
        
        if duckdb is None or not parquet_path.exists():
            return jsonify({
                'success': False,
                'error': 'Parquet 数据文件不存在',
                'data': []
            }), 500
        
        parquet_str = str(parquet_path).replace('\\', '/')
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 构建 WHERE 条件
        where_conditions = [
            "TRY_CAST(post_publish_time AS TIMESTAMP) IS NOT NULL",
            f"CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) >= '{start_date_str}'",
            f"CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) <= '{end_date_str}'"
        ]
        
        # 如果提供了 symbol，添加股票过滤条件
        if symbol:
            # 提取6位数字代码
            if symbol.startswith('sz') or symbol.startswith('sh'):
                code_6 = symbol[2:] if len(symbol) > 2 else symbol
                full_symbol = symbol
            else:
                code_6 = symbol[-6:] if len(symbol) >= 6 else symbol.zfill(6)
                full_symbol = symbol
            
            symbol_conditions = [
                f"symbol = '{full_symbol}'",
                f"symbol = '{code_6}'",
                f"RIGHT(symbol, 6) = '{code_6}'",
                f"stockbar_code = '{code_6}'",
                f"symbol LIKE '%{code_6}%'"
            ]
            where_conditions.append(f"({' OR '.join(symbol_conditions)})")
        
        where_clause = ' AND '.join(where_conditions)
        
        # 按日期分组，统计每天的帖子数量和平均情感得分
        sql = f"""
            SELECT
                CAST(TRY_CAST(post_publish_time AS TIMESTAMP) AS DATE) AS date,
                COUNT(*) AS post_count,
                COALESCE(AVG(TRY_CAST(bullish_bearish AS DOUBLE)), 0.0) AS avg_sentiment
            FROM read_parquet('{parquet_str}')
            WHERE {where_clause}
            GROUP BY date
            ORDER BY date ASC
        """
        
        con = duckdb.connect()
        try:
            con.execute("SET threads TO 4")
            con.execute("SET memory_limit='2GB'")
            df = con.execute(sql).df()
        finally:
            con.close()
        
        # 转换为前端需要的格式
        data = []
        if not df.empty:
            for _, row in df.iterrows():
                date_val = row.get('date')
                if pd.isna(date_val):
                    continue
                
                # 格式化日期
                if isinstance(date_val, pd.Timestamp):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                
                data.append({
                    'date': date_str,
                    'post_count': int(row.get('post_count', 0)),
                    'avg_sentiment': round(float(row.get('avg_sentiment', 0.0)), 3)
                })
        
        # 确保按日期排序（虽然 SQL 已经排序了，但这里再确保一次）
        data.sort(key=lambda x: x['date'])
        
        return jsonify({
            'success': True,
            'data': data,
            'message': f'Successfully retrieved sentiment trend for {symbol or "all stocks"}'
        })
    except Exception as e:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取情感趋势数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'data': []
        }), 500

@app.route('/api/lda_topics', methods=['GET'])
def get_lda_topics():
    """获取LDA主题分布数据"""
    try:
        symbol = request.args.get('symbol')
        
        # 模拟5个主题及其分布
        topics = [
            {'topic': '短期炒作', 'weight': random.uniform(0.1, 0.4)},
            {'topic': '业绩利好', 'weight': random.uniform(0.1, 0.3)},
            {'topic': '主力出货', 'weight': random.uniform(0.05, 0.25)},
            {'topic': '重组传闻', 'weight': random.uniform(0.05, 0.2)},
            {'topic': '散户被套', 'weight': random.uniform(0.05, 0.2)}
        ]
        
        # 归一化权重
        total = sum(t['weight'] for t in topics)
        for t in topics:
            t['weight'] = round(t['weight'] / total, 2)
        
        # 按权重排序
        topics_sorted = sorted(topics, key=lambda x: x['weight'], reverse=True)
        
        # 转换为前端期望的格式
        topic_names = [t['topic'] for t in topics_sorted]
        topic_scores = [t['weight'] for t in topics_sorted]
        
        return jsonify({
            'success': True,
            'data': {
                'topics': topic_names,
                'scores': topic_scores
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/scatter_data', methods=['GET'])
def get_scatter_data():
    """获取情感-热度散点图数据 - 重构后：委托给 visualization_api"""
    from utils.logger import get_logger
    logger = get_logger(__name__)
    
    try:
        symbol = request.args.get('symbol')
        logger.info(f"开始获取散点图数据: symbol={symbol}")
        
        # CHANGED: 使用线程池执行，添加超时控制
        import concurrent.futures
        import threading
        
        def execute_query():
            """在单独线程中执行查询"""
            return api.get_scatter_data(symbol)
        
        # 使用线程池执行，设置60秒超时
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute_query)
            try:
                result = future.result(timeout=60.0)  # 60秒超时
                logger.info(f"散点图数据获取成功: {len(result.get('data', []))} 条记录")
                return jsonify(result)
            except concurrent.futures.TimeoutError:
                logger.warning("散点图数据查询超时（超过60秒）")
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


if __name__ == '__main__':
    print('🚀 启动量化回测数据可视化API服务...')
    # 在启动服务前预先初始化 API（替代 @app.before_first_request）
    _ensure_api_initialized()
    # 启动 Redis 订阅线程（用于接收 Worker 进程的进度消息）
    start_redis_subscriber()
    # 必须使用 socketio.run 才能启用 Socket.IO 事件
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
