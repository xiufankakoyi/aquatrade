# backtest/flexible_backtest_engine.py
"""
灵活的回测引擎 - 解决"缺乏扩展性"问题

设计理念：
- 支持多种时间粒度（日线、分钟线等）
- 使用 datetime 对象而不是字符串，更灵活
- 支持流式处理，避免内存溢出
- 可扩展到分时级别回测

改进点：
1. 时间粒度抽象：支持 'daily', 'minute', 'tick' 等
2. datetime 对象：统一使用 pd.Timestamp 处理时间
3. 流式数据加载：按需加载，避免 OOM
4. 可扩展架构：易于添加新的时间粒度支持
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Generator, Any, Union
from datetime import datetime, timedelta
from threading import Event
# from tqdm import tqdm  # Removed - causing blocking in Honcho
import time
import json
from functools import lru_cache

# 【性能加速】导入 Numba 和 Polars
try:
    import numba as nb
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    njit = lambda *args, **kwargs: (lambda f: f)

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None


def _make_json_serializable(obj: Any, max_depth: int = 10, _current_depth: int = 0) -> Any:
    """
    递归将对象转换为 JSON 可序列化的类型。
    
    处理以下类型：
    - 基本类型：int, float, str, bool, None（直接返回）
    - 列表/元组：递归处理每个元素
    - 字典：递归处理每个值
    - numpy 数组：调用 tolist()
    - pandas 对象：DataFrame/Series 转为 dict，Timestamp 转为 ISO 字符串
    - datetime/date 对象：转为 ISO 字符串
    - set/frozenset：转为排序后的列表
    - 具有 __dict__ 的对象：递归处理属性
    - 未知类型：尝试 str()，失败返回 None
    
    参数:
        obj: 要序列化的对象
        max_depth: 最大递归深度（防止无限递归）
        _current_depth: 当前递归深度（内部使用）
    
    返回:
        JSON 可序列化的对象
    """
    # 防止无限递归
    if _current_depth > max_depth:
        return None
    
    # [Modified] 任务D：JSON兼容性加固 - 添加isinf检查
    # 基本类型直接返回，但需处理无穷大值
    if obj is None or isinstance(obj, bool):
        return obj
    elif isinstance(obj, (int, float)):
        # 处理无穷大值：isinf -> None
        import math
        if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
            return None
        elif hasattr(obj, 'item'):  # numpy 标量
            try:
                val = obj.item()
                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                    return None
            except:
                pass
        return obj
    elif isinstance(obj, str):
        return obj
    
    # 处理 numpy 类型
    if hasattr(obj, 'tolist'):
        try:
            return obj.tolist()
        except (AttributeError, ValueError):
            pass
    elif isinstance(obj, np.generic):
        # numpy 标量类型
        try:
            return float(obj) if isinstance(obj, (np.floating, np.integer)) else str(obj)
        except (ValueError, TypeError):
            return None
    
    # 处理 pandas DataFrame 和 Series
    if isinstance(obj, pd.DataFrame):
        return _make_json_serializable(obj.to_dict('records'), max_depth, _current_depth)
    if isinstance(obj, pd.Series):
        return _make_json_serializable(obj.to_dict(), max_depth, _current_depth)
    
    # 处理 pandas 特定类型
    if isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        try:
            return obj.isoformat()
        except (AttributeError, ValueError):
            return str(obj)
    if isinstance(obj, (pd.Period, pd.Interval)):
        return str(obj)
    
    # 处理 datetime/date 对象
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # 处理列表和元组
    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            try:
                result.append(_make_json_serializable(item, max_depth, _current_depth + 1))
            except Exception:
                result.append(str(item))
        return result if isinstance(obj, list) else tuple(result)
    
    # 处理字典
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            try:
                # 确保 key 也是可序列化的
                key = _make_json_serializable(k, max_depth, _current_depth + 1) if not isinstance(k, (str, int, float, bool)) else k
                if key is not None:
                    result[key] = _make_json_serializable(v, max_depth, _current_depth + 1)
            except Exception:
                pass
        return result
    
    # 处理 set/frozenset
    if isinstance(obj, (set, frozenset)):
        try:
            sorted_items = sorted(_make_json_serializable(list(obj), max_depth, _current_depth + 1))
            return sorted_items
        except (TypeError, ValueError):
            return list(obj)
    
    # 处理具有 __dict__ 的对象
    if hasattr(obj, '__dict__'):
        try:
            result = {}
            for k, v in obj.__dict__.items():
                # 跳过私有属性和不可序列化的属性
                if k.startswith('_'):
                    continue
                try:
                    result[k] = _make_json_serializable(v, max_depth, _current_depth + 1)
                except Exception:
                    pass
            return result
        except Exception:
            pass
    
    # 最后尝试 str()
    try:
        return str(obj)
    except Exception:
        return None


def _detect_architecture(data_query, stock_pool=None):
    """
    检测当前使用的架构
    
    Returns:
        dict: 架构信息
    """
    arch = {
        'engine': 'FlexibleBacktestEngine',
        'data_backend': 'unknown',
        'data_format': 'unknown',
        'compute_backend': 'unknown',
        'numba_active': False,
        'preloaded': False,
        'use_pl': False
    }
    
    # 1. 检测数据后端 (QuestDB/LanceDB/DuckDB/SQLite)
    if hasattr(data_query, '_use_questdb') and data_query._use_questdb:
        arch['data_backend'] = 'QuestDB'
    elif hasattr(data_query, '_use_lancedb') and data_query._use_lancedb:
        arch['data_backend'] = 'LanceDB'
    elif hasattr(data_query, '_use_duckdb') and data_query._use_duckdb:
        arch['data_backend'] = 'DuckDB'
    else:
        arch['data_backend'] = 'SQLite/Other'
    
    # 2. 检测数据格式 (Pandas/Polars/NumPy)
    if stock_pool is not None:
        try:
            import pandas as pd
            import polars as pl
            import numpy as np
            
            if isinstance(stock_pool, pd.DataFrame):
                arch['data_format'] = 'Pandas DataFrame'
            elif isinstance(stock_pool, pl.DataFrame):
                arch['data_format'] = 'Polars DataFrame'
                arch['use_pl'] = True
            elif isinstance(stock_pool, pl.LazyFrame):
                arch['data_format'] = 'Polars LazyFrame'
                arch['use_pl'] = True
            elif isinstance(stock_pool, np.ndarray):
                arch['data_format'] = 'NumPy Array'
            else:
                arch['data_format'] = str(type(stock_pool).__name__)
        except ImportError:
            arch['data_format'] = 'Library missing'
    
    # 3. 检测计算后端 (Numba)
    try:
        import numba
        arch['compute_backend'] = 'Numba JIT'
        arch['numba_active'] = True
    except ImportError:
        arch['compute_backend'] = 'Python'
        arch['numba_active'] = False
    
    # 4. 检测是否使用预加载 (Polars 或 Pandas)
    has_pl_cache = hasattr(data_query, '_preloaded_data_pl') and data_query._preloaded_data_pl is not None
    has_pd_cache = hasattr(data_query, '_preloaded_data') and data_query._preloaded_data is not None
    
    if has_pl_cache:
        arch['preloaded'] = 'Polars Native'
    elif has_pd_cache:
        arch['preloaded'] = 'Pandas Cache'
    else:
        arch['preloaded'] = False
    
    return arch


class FlexibleBacktestEngine:
    """
    灵活的回测引擎
    
    支持：
    - 多种时间粒度（日线、分钟线、tick）
    - datetime 对象统一处理
    - 流式数据加载
    - 可扩展到分时级别
    """
    
    def __init__(
        self,
        data_query,
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        time_granularity: str = 'daily'
    ):
        """
        参数：
            data_query: 数据查询对象
            initial_capital: 初始资金
            commission_rate: 手续费率（默认0.03%）
            min_commission: 最小手续费（默认5元）
            time_granularity: 时间粒度 ('daily', 'minute', 'tick')
        """
        self.data_query = data_query
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.time_granularity = time_granularity
        
        # 权益曲线追踪
        self._equity_history = []  # 存储 (日期, 权益值) 元组列表
        
        # 数据查询缓存（实例级别LRU缓存）
        self._stock_pool_cache = {}  # {date_str: DataFrame}
        self._trading_dates_cache = None  # 缓存交易日列表
        self._cache_max_size = 1000  # 最大缓存日期数量（LRU淘汰阈值）
        self._price_map_cache = {}  # 价格映射缓存
        self._cache_order = []  # 缓存访问顺序列表，用于LRU淘汰
        
        # 向量化模式标志（性能优化）
        self._vectorized_mode = False  # 是否启用向量化信号生成
        self._signal_matrix = None  # 预计算的信号矩阵 (T, N)
        self._stock_codes_list = None  # 股票代码列表
        
        
        # 初始化前一日数据追踪（用于分红检测）
        prev_day_data = {}
        
        # 验证时间粒度
        valid_granularities = ['daily', 'minute', 'tick']
        if time_granularity not in valid_granularities:
            raise ValueError(
                f"不支持的时间粒度: {time_granularity}。"
                f"支持: {valid_granularities}"
            )
    
    def run_backtest_streaming(
        self,
        start_date: Union[str, pd.Timestamp, datetime],
        end_date: Union[str, pd.Timestamp, datetime],
        strategy,
        stop_event: Optional[Event] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式回测生成器（支持多种时间粒度）
        
        参数：
            start_date: 开始日期（支持 str, pd.Timestamp, datetime）
            end_date: 结束日期
            strategy: 策略对象
            stop_event: 停止事件
        
        返回：
            Generator，产出回测更新事件
        """
        # 统一转换为 pd.Timestamp
        start_ts = self._normalize_datetime(start_date)
        end_ts = self._normalize_datetime(end_date)
        
        if start_ts >= end_ts:
            yield {
                "type": "error",
                "data": {"message": "开始日期必须早于结束日期"}
            }
            return
        
        # 根据时间粒度获取时间序列
        time_series = self._get_time_series(start_ts, end_ts)
        
        if not time_series:
            yield {
                "type": "error",
                "data": {"message": "未找到有效的时间序列"}
            }
            return
        
        # 初始化账户
        portfolio = {}
        cash = self.initial_capital
        results_list = []
        all_trades_log = []
        total_value = self.initial_capital  # 初始化 total_value
        position_info = {}  # 【修复】跟踪每个持仓的成本基础和入场日期
        prev_day_data = {}  # 初始化前一日数据追踪（用于分红检测）
        
        # 产出开始信号
        yield {
            "type": "backtest_start",
            "data": {
                "initialCapital": self.initial_capital,
                "timeGranularity": self.time_granularity,
                "startDate": start_ts.strftime("%Y-%m-%d"),
                "endDate": end_ts.strftime("%Y-%m-%d")
            }
        }
        
        # 1. 预加载整个回测期间的数据（如果支持）
        preloaded_data = None
        if hasattr(self.data_query, 'get_all_daily_data_for_period'):
            try:
                # 【预热期修复】向前多加载 30 个交易日的数据，确保指标完成计算
                warmup_days = 30
                try:
                    # 获取较早的交易日作为预热起点
                    hist_dates = self.data_query.get_trading_dates(
                        (start_ts - timedelta(days=60)).strftime("%Y-%m-%d"),
                        (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
                    )
                    if len(hist_dates) >= warmup_days:
                        load_start_date_str = hist_dates[-warmup_days]
                    elif hist_dates:
                        load_start_date_str = hist_dates[0]
                    else:
                        load_start_date_str = start_ts.strftime("%Y-%m-%d")
                except Exception:
                    load_start_date_str = (start_ts - timedelta(days=warmup_days * 1.5)).strftime("%Y-%m-%d")
                
                # 显式触发预加载，利用 LanceDB + Polars 的极速能力
                self.data_query.preload_backtest_data(load_start_date_str, end_ts.strftime("%Y-%m-%d"))
                preloaded_data = getattr(self.data_query, '_preloaded_data', None)
                if preloaded_data is not None:
                    print(f"[Engine] 成功预加载 {len(preloaded_data)} 个数据点 (含预热期 {load_start_date_str})，回测将全程从内存读取。")
            except Exception as e:
                print(f"[Engine] 预加载失败，将回退到实时查询逻辑: {e}")
        
        # 【性能优化】清除因子计算缓存，确保每次回测都是干净的
        from core.strategies.utils.factor_loader import FactorLoader
        FactorLoader.clear_cache()
        
        # 流式循环
        perf_snapshots = []
        total_steps = len(time_series)
        for idx, current_time in enumerate(time_series, 1):
            if stop_event and stop_event.is_set():
                yield {"type": "backtest_cancelled", "data": {"message": "回测已取消"}}
                return
            
            # 性能分析：记录每天的总耗时
            day_start = time.perf_counter()
            perf_breakdown = {}
            arch_info = {}
            
            # 初始化 logger（延迟导入避免循环依赖）
            from config.logger import get_logger
            logger = get_logger(__name__)
            
            try:
                # 获取当前时间点的数据
                t0 = time.perf_counter()
                
                # 【优化】优先尝试 Polars 路径 (零拷贝)
                use_pl = False
                stock_pool = None
                if hasattr(self.data_query, 'get_stock_pool_pl'):
                    stock_pool = self.data_query.get_stock_pool_pl(current_time.strftime("%Y-%m-%d"))
                    if stock_pool is not None and not stock_pool.is_empty():
                        # 【核心兼容性修复】如果策略不支持 Polars，则强制转换为 Pandas
                        if not getattr(strategy, 'prefer_polars', False):
                            stock_pool = stock_pool.to_pandas()
                            use_pl = False
                        else:
                            use_pl = True
                
                if not use_pl and (stock_pool is None or (hasattr(stock_pool, 'is_empty') and stock_pool.is_empty())):
                    stock_pool = self._get_stock_pool_at_time(current_time, self.data_query)
                
                # 【性能优化】预加载当日数据字典，用于快速索引价格和分红
                # 无论 stock_pool 是 Polars 还是 Pandas，都转换为 Dict 可以避免循环内 filter/iloc
                current_day_data_dict = {}
                if use_pl:
                    # Polars 极速转换: 只取需要的列
                    needed_pl_cols = [c for c in ['stock_code', 'close', 'open', 'adj_factor', 'total_mv', 'is_suspended', 'is_limit_up', 'is_limit_down'] if c in stock_pool.columns]
                    current_day_data_dict = {
                        str(row[0]): dict(zip(needed_pl_cols, row)) 
                        for row in stock_pool.select(needed_pl_cols).iter_rows()
                    }
                else:
                    if stock_pool is not None and not stock_pool.empty:
                        # Pandas 转换
                        current_day_data_dict = stock_pool.set_index('stock_code').to_dict('index')

                perf_breakdown['data_load'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 检测架构（仅在第一天或每10天检测一次）
                if idx == 1 or idx % 10 == 0:
                    arch_info = _detect_architecture(self.data_query, stock_pool)
                
                if stock_pool is None or (use_pl and stock_pool.is_empty()) or (not use_pl and stock_pool.empty):
                    continue
                
                # 设置策略上下文
                t0 = time.perf_counter()
                strategy.set_runtime_context(
                    current_date=current_time.strftime("%Y-%m-%d"),
                    portfolio=portfolio,
                    cash=cash
                )
                perf_breakdown['set_context'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 生成信号
                t0 = time.perf_counter()
                
                # 【性能优化】检测策略是否支持向量化信号生成
                # 如果支持且有预加载数据，使用向量化路径（性能提升 40-100x）
                if (hasattr(strategy, 'generate_signals_vectorized') and 
                    preloaded_data is not None and 
                    idx == 1):  # 只在第一天检测并切换到向量化模式
                    
                    # 构建向量化所需的数据结构
                    # 【关键】使用包含预热期的全量交易日列表进行信号生成
                    trading_dates_list = sorted(preloaded_data.keys())
                    
                    # 【重要修复】从预加载数据的所有日期中收集股票代码列表
                    # 之前只用第一天，导致如果第一天股票不全，后续交易会被忽略
                    all_codes = set()
                    for df in preloaded_data.values():
                        if df is not None and not df.empty:
                            all_codes.update(df['stock_code'].unique())
                    stock_codes_list = sorted(list(all_codes))
                    
                    # 构建价格矩阵 (T, N, 4) - [open, high, low, close]
                    T = len(trading_dates_list)
                    N = len(stock_codes_list)
                    price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
                    
                    # 【性能优化】使用向量化操作填充价格矩阵，避免慢速的 iterrows()
                    # 创建股票代码到索引的映射
                    code_to_idx = {code: i for i, code in enumerate(stock_codes_list)}
                    date_to_idx = {date: i for i, date in enumerate(trading_dates_list)}
                    
                    # 合并所有日期的数据到一个大DataFrame
                    all_data_list = []
                    for date_str, df_day in preloaded_data.items():
                        if df_day is not None and not df_day.empty and date_str in date_to_idx:
                            df_copy = df_day[['stock_code', 'open', 'high', 'low', 'close']].copy()
                            df_copy['date_idx'] = date_to_idx[date_str]
                            all_data_list.append(df_copy)
                    
                    if all_data_list:
                        all_data_df = pd.concat(all_data_list, ignore_index=True)
                        
                        # 【数据清洗】去除空格，并建立索引映射
                        all_data_df['stock_code'] = all_data_df['stock_code'].astype(str).str.strip()
                        # stock_codes_list 已经在上面处理过或可以再次处理以确保一致性
                        
                        # 【核心修复】创建 code_idx 列以便后续向量化填充
                        all_data_df['code_idx'] = all_data_df['stock_code'].map(code_to_idx)
                        
                        # 过滤掉无法匹配的非法代码
                        all_data_df = all_data_df.dropna(subset=['code_idx'])
                        
                        if not all_data_df.empty:
                            all_data_df['code_idx'] = all_data_df['code_idx'].astype(int)
                            
                            # 使用NumPy高级索引一次性填充所有数据
                            t_indices = all_data_df['date_idx'].values.astype(int)
                            n_indices = all_data_df['code_idx'].values
                            
                            price_matrix[t_indices, n_indices, 0] = all_data_df['open'].values
                            price_matrix[t_indices, n_indices, 1] = all_data_df['high'].values
                            price_matrix[t_indices, n_indices, 2] = all_data_df['low'].values
                            price_matrix[t_indices, n_indices, 3] = all_data_df['close'].values
                        
                    # 调用向量化信号生成
                    logger.info(f"[Engine] 向量化参数: T={T} days, N={N} stocks")
                    signal_matrix = strategy.generate_signals_vectorized(
                        price_matrix=price_matrix,
                        trading_dates=trading_dates_list,
                        stock_codes=stock_codes_list,
                        data_query=self.data_query,
                        preloaded_data=preloaded_data
                    )
                    
                    # 将信号矩阵转换为当前日期的信号字典
                    # signal_matrix[t, n]: 0=hold, 1=buy, 2=sell
                    t_idx = idx - 1  # 当前是第几天（0-indexed）
                    signals = {}
                    for n, code in enumerate(stock_codes_list):
                        sig_val = signal_matrix[t_idx, n]
                        if sig_val == 1:
                            # 携带指标快照
                            indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                            signals[code] = {'action': 'buy', 'indicators': indicators}
                        elif sig_val == 2:
                            indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                            signals[code] = {'action': 'sell', 'indicators': indicators}
                    
                    # 标记为向量化模式，后续循环直接从 signal_matrix 读取
                    self._vectorized_mode = True
                    self._signal_matrix = signal_matrix
                    self._stock_codes_list = stock_codes_list
                    # 【关键】保存全量日期映射，以便主循环精确定位信号索引
                    self._date_to_idx = {d: i for i, d in enumerate(trading_dates_list)}
                    
                    # 取当前日期对应的信号
                    current_date_str = current_time.strftime("%Y-%m-%d")
                    t_idx = self._date_to_idx.get(current_date_str, 0)
                    
                    signals = {}
                    for n, code in enumerate(stock_codes_list):
                        sig_val = signal_matrix[t_idx, n]
                        if sig_val == 1:
                            # 携带指标快照
                            indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                            signals[code] = {'action': 'buy', 'indicators': indicators}
                        elif sig_val == 2:
                            indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                            signals[code] = {'action': 'sell', 'indicators': indicators}
                    
                    logger.info(f"[Engine] 向量化信号生成完成({len(trading_dates_list)}天)，起始索引: {t_idx}，当前日期信号: {len(signals)} 个")
                    
                elif hasattr(self, '_vectorized_mode') and self._vectorized_mode:
                    # 向量化模式已启用，直接从预计算的信号矩阵读取
                    current_date_str = current_time.strftime("%Y-%m-%d")
                    t_idx = self._date_to_idx.get(current_date_str, -1)
                    
                    signals = {}
                    if t_idx >= 0:
                        for n, code in enumerate(self._stock_codes_list):
                            sig_val = self._signal_matrix[t_idx, n]
                            if sig_val == 1:
                                indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                                signals[code] = {'action': 'buy', 'indicators': indicators}
                            elif sig_val == 2:
                                indicators = strategy.get_indicators_at(t_idx, n) if hasattr(strategy, 'get_indicators_at') else {}
                                signals[code] = {'action': 'sell', 'indicators': indicators}
                else:
                    # 传统模式：逐日生成信号
                    signals = strategy.generate_signals(
                        current_date=current_time.strftime("%Y-%m-%d"),
                        stock_pool_today=stock_pool,
                        data_query=self.data_query
                    )
                
                perf_breakdown['signal_generation'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 执行交易
                portfolio, cash, trades, position_info = self._execute_trades(
                    current_time,
                    stock_pool,
                    signals,
                    portfolio,
                    cash,
                    position_info,  # 【修复】传递 position_info
                    strategy  # 【仓位管理修复】传递strategy实例
                )
                perf_breakdown['execute_trades'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 记录交易
                t0 = time.perf_counter()
                all_trades_log.extend(trades)
                
                # 【新增】详细日志：记录每笔交易
                if trades:
                    for trade in trades:
                        action_cn = "买入" if trade.get('action') == 'buy' else "卖出"
                        logger.info(f"[TRADE] {current_time.strftime('%Y-%m-%d')} {action_cn} {trade.get('code')}: "
                                   f"{trade.get('shares')}股 @ {trade.get('price'):.2f}")
                        if trade.get('action') == 'sell' and 'profit_loss' in trade:
                            logger.info(f"   PnL: {trade.get('profit_loss'):,.2f} (ROI: {trade.get('roi', 0):.2f}%)")
                
                # 【修复】立即产出交易事件，供前端实时显示
                for trade in trades:
                    logger.debug(f"[TRACE] Engine yielding new_trade: {trade.get('code')} {trade.get('action')} {trade.get('shares')} shares")
                    
                    # 【核心修复】映射字段名以匹配 frontend expectations (useStreamingBacktest.ts)
                    # frontend 期望 symbolCode, quantity, profitLoss 等
                    # 【Bug修复】确保股票代码补齐到6位，避免00开头股票丢失前导零
                    stock_code = str(trade.get('code', ''))
                    padded_code = stock_code.zfill(6) if stock_code.isdigit() else stock_code
                    
                    trade_to_yield = {
                        **trade,
                        "symbolCode": padded_code,
                        "symbol": padded_code,
                        "code": padded_code,  # 也更新code字段保持一致
                        "quantity": trade.get('shares'),
                        "profitLoss": trade.get('profit_loss', 0.0),
                        "id": f"{trade.get('date')}-{padded_code}-{trade.get('action')}"
                    }
                    
                    yield {
                        "type": "new_trade_engine",
                        "data": trade_to_yield
                    }
                    
                perf_breakdown['log_trades'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 计算账户价值
                t0 = time.perf_counter()
                portfolio_value = self._calculate_portfolio_value(
                    current_time,
                    portfolio,
                    stock_pool,
                    use_pl=use_pl,
                    data_dict=current_day_data_dict  # 使用预计算字典
                )
                total_value = cash + portfolio_value
                perf_breakdown['calc_value'] = (time.perf_counter() - t0) * 1000  # ms
                
                # --- 【新增】自动分红结算逻辑 ---
                # 逻辑：检查持仓股票是否发生除权变化 (adj_factor 变动)
                if portfolio and prev_day_data:
                    dividend_t0 = time.perf_counter()
                    total_dividends_today = 0.0
                    
                    for code, shares in portfolio.items():
                        if code in prev_day_data and code in current_day_data_dict:
                            prev_factor = float(prev_day_data[code].get('adj_factor', 1.0))
                            curr_factor = float(current_day_data_dict[code].get('adj_factor', 1.0))
                            
                            # 检测到因子变化 -> 发生除权/拆股
                            if abs(curr_factor - prev_factor) > 1e-6:
                                # 区分“送转/拆股”与“现金分红”
                                # 算法：检查总股本变化。现金分红不改变总股本。
                                # 总股本 = total_mv / close
                                prev_close = float(prev_day_data[code].get('close', 0))
                                curr_close = float(current_day_data_dict[code].get('close', 0))
                                
                                # 这里使用 total_mv 作为股本代理（假设 mv 变化主要来自价格变动和分红）
                                # 更准确的方法是 check total_shares = total_mv / close
                                prev_mv = float(prev_day_data[code].get('total_mv', 0))
                                curr_mv = float(current_day_data_dict[code].get('total_mv', 0))
                                
                                prev_shares_total = prev_mv / prev_close if prev_close > 0 else 0
                                curr_shares_total = curr_mv / curr_close if curr_close > 0 else 0
                                
                                # 如果总股本变化比例很小（<5%），视为现金分红，而非拆股/送股
                                shares_change_ratio = abs(curr_shares_total / prev_shares_total - 1) if prev_shares_total > 0 else 0
                                
                                if shares_change_ratio < 0.05:
                                    # 1. 纯现金分红逻辑
                                    # 公式：每股分红 = 昨日收盘价 * (1 - 昨日因子/今日因子)
                                    dividend_per_share = prev_close * (1 - prev_factor / curr_factor)
                                    if dividend_per_share > 0:
                                        total_dividend = shares * dividend_per_share
                                        cash += total_dividend
                                        total_dividends_today += total_dividend
                                        
                                        logger.info(f"🧧 [分红入账] {current_time.strftime('%Y-%m-%d')} {code}: "
                                                   f"持有 {shares} 股，每股派息 ¥{dividend_per_share:.4f}，"
                                                   f"总计 ¥{total_dividend:.2f}")
                                        
                                        # 更新总价值（现金增加了）
                                        total_value += total_dividend
                                        
                                        yield {
                                            "type": "dividend_payout",
                                            "data": {
                                                "date": current_time.strftime("%Y-%m-%d"),
                                                "code": code,
                                                "type": "cash",
                                                "dividend": total_dividend,
                                                "dividend_per_share": dividend_per_share
                                            }
                                        }
                                else:
                                    # 2. 送转/拆股逻辑 (非现金，仅改变持仓股数)
                                    # 公式：新股数 = 原股数 * (今日因子 / 昨日因子)
                                    # 注意：因子增加表示价格被“摊薄”，股数按比例增加
                                    new_shares = int(round(shares * (curr_factor / prev_factor)))
                                    if new_shares != shares:
                                        portfolio[code] = new_shares
                                        logger.info(f"🍀 [送转/拆股] {current_time.strftime('%Y-%m-%d')} {code}: "
                                                   f"股数由 {shares} -> {new_shares} (因子变动: {prev_factor:.4f}->{curr_factor:.4f})")
                                        
                                        yield {
                                            "type": "dividend_payout",
                                            "data": {
                                                "date": current_time.strftime("%Y-%m-%d"),
                                                "code": code,
                                                "type": "split",
                                                "old_shares": shares,
                                                "new_shares": new_shares
                                            }
                                        }
                    
                    perf_breakdown['dividend_settlement'] = (time.perf_counter() - dividend_t0) * 1000
                
                # 更新前一日数据追踪
                if isinstance(stock_pool, pd.DataFrame):
                    prev_day_data = stock_pool.set_index('stock_code').to_dict('index')
                else:
                    prev_day_data = stock_pool.to_pandas().set_index('stock_code').to_dict('index')
                
                # 记录权益曲线（每日）
                if self.time_granularity == 'daily' or idx % self._get_update_frequency() == 0:
                    # 记录到权益历史
                    self._equity_history.append((
                        current_time.strftime("%Y-%m-%d"),
                        total_value
                    ))
                
                # 产出每日更新
                t0 = time.perf_counter()
                if self.time_granularity == 'daily' or idx % self._get_update_frequency() == 0:
                    yield {
                        "type": "daily_equity_engine",
                        "data": {
                            "date": current_time.strftime("%Y-%m-%d"),
                            "equity": total_value,
                            "strategyReturn": total_value,  # 【修复】同步输出 strategyReturn 键，避免 KeyError
                            "cash": cash,
                            "positions": len(portfolio),
                            "trades": len(trades)
                        }
                    }
                perf_breakdown['yield_data'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 计算总耗时
                perf_breakdown['total'] = (time.perf_counter() - day_start) * 1000  # ms
                
                # 收集性能快照
                perf_snapshots.append({
                    "day": idx,
                    "date": current_time.strftime('%Y-%m-%d'),
                    "metrics": perf_breakdown
                })

                # 【新增】定期发射进度事件
                if idx % 5 == 0 or idx == total_steps:
                    yield {
                        "type": "progress",
                        "data": {"progress": round((idx / total_steps) * 100, 1)}
                    }

                # 输出性能分析（仅在首尾或超过阈值时输出）
                # 策略一：控制台使用“异常阈值”过滤 (Threshold Logging)
                PERF_THRESHOLD_MS = 200
                is_slow_day = perf_breakdown['total'] > PERF_THRESHOLD_MS
                is_first_day = idx == 1
                is_last_day = idx == len(time_series)
                
                if is_first_day or is_last_day or is_slow_day:
                    # 构建架构信息字符串
                    arch_str = ""
                    if arch_info:
                        arch_str = f" | 架构: {arch_info.get('data_backend', '?')}/{arch_info.get('data_format', '?')}"
                        if arch_info.get('preloaded'):
                            arch_str += " [预加载]"
                    
                    log_level = logger.warning if (is_slow_day or is_first_day) else logger.info
                    log_msg = (f"[PERF][Day {idx}] {current_time.strftime('%Y-%m-%d')}: "
                          f"总耗时={perf_breakdown['total']:.1f}ms | "
                          f"数据加载={perf_breakdown['data_load']:.1f}ms | "
                          f"信号生成={perf_breakdown['signal_generation']:.1f}ms | "
                          f"交易执行={perf_breakdown['execute_trades']:.1f}ms | "
                          f"价值计算={perf_breakdown['calc_value']:.1f}ms{arch_str}")
                    
                    if is_slow_day and not is_first_day:
                        log_msg += " [SLOW]"
                        
                    log_level(log_msg)
                    
                    # 如果是第一天，输出详细的架构信息
                    if is_first_day and arch_info:
                        logger.info(f"[ARCH] ========== 回测引擎架构检测 ==========")
                        logger.info(f"[ARCH] 引擎: {arch_info.get('engine', '?')}")
                        logger.info(f"[ARCH] 数据后端: {arch_info.get('data_backend', '?')}")
                        logger.info(f"[ARCH] 数据格式: {arch_info.get('data_format', '?')}")
                        logger.info(f"[ARCH] 计算后端: {arch_info.get('compute_backend', '?')}")
                        logger.info(f"[ARCH] 数据预加载: {'是' if arch_info.get('preloaded') else '否'}")
                        logger.info(f"[ARCH] ======================================")
                
            except Exception as e:
                yield {
                    "type": "error",
                    "data": {"message": f"回测过程中出错: {str(e)}"}
                }
                import traceback
                traceback.print_exc()
        
        # 策略三：结构化性能快照 (Structured Snapshot)
        # Action: 回测结束时，生成一个 JSON 文件 perf_report_run_id.json。
        try:
            import json
            import os
            from config.config import Config  # Import here to ensure it's available
            run_id = int(time.time())
            perf_report_file = os.path.join(os.path.dirname(Config.DB_PATH), f"perf_report_{run_id}.json")
            with open(perf_report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "strategy": getattr(strategy, 'strategy_name', 'Unknown'),
                    "granularity": self.time_granularity,
                    "snapshots": perf_snapshots
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"[PERF] 完整性能报告已保存至: {perf_report_file}")
        except Exception as e:
            logger.error(f"[PERF] 保存性能报告失败: {e}")


        # 计算最终指标
        # ========================
        
        # 从交易记录计算胜率和盈亏比
        sell_trades = [t for t in all_trades_log if t.get('action') == 'sell']
        trade_count = len(sell_trades)
        
        # 计算盈亏
        total_profit = 0.0
        total_loss = 0.0
        win_trades = 0
        
        for trade in sell_trades:
            # 尝试获取回测引擎计算的盈亏
            pnl = trade.get('profit_loss', 0)
            if pnl == 0:
                # 如果没有profit_loss，使用roi计算
                roi = trade.get('roi', 0)
                cost = trade.get('cost', 0)
                if roi != 0 and cost != 0:
                    pnl = (roi / 100) * cost
            
            if pnl > 0:
                total_profit += pnl
                win_trades += 1
            elif pnl < 0:
                total_loss += abs(pnl)
        
        # 计算胜率和盈亏比
        win_rate = (win_trades / trade_count * 100) if trade_count > 0 else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit / 1.0 if total_profit > 0 else 0.0)
        
        # 生成权益曲线数据
        equity_curve_data = []
        if hasattr(self, '_equity_history') and self._equity_history:
            for date, value in self._equity_history:
                equity_curve_data.append({
                    "date": date if isinstance(date, str) else date.strftime("%Y-%m-%d"),
                    "equity": round(value, 2)
                })
        
        # 【修复】计算最大回撤从权益历史
        max_drawdown = 0.0
        if hasattr(self, '_equity_history') and self._equity_history:
            equity_values = [v for _, v in self._equity_history]
            if equity_values:
                peak = equity_values[0]
                for value in equity_values:
                    if value > peak:
                        peak = value
                    if peak > 0:  # 避免除零
                        drawdown = (value - peak) / peak * 100
                        if drawdown < max_drawdown:
                            max_drawdown = drawdown
        
        
        # 计算总收益率
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100
        
        # 计算年化收益率
        days = (end_ts - start_ts).days
        years = days / 365.25
        annual_return = 0.0
        if years > 0:
            annual_return = ((total_value / self.initial_capital) ** (1 / years) - 1) * 100
        else:
            annual_return = total_return
        
        # 计算风险指标 (Sharpe, Sortino, Volatility)
        # 从权益历史计算日收益率
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        volatility = 0.0
        calmar_ratio = 0.0
        
        if hasattr(self, '_equity_history') and len(self._equity_history) > 1:
            try:
                # 提取权益值序列
                equity_series = pd.Series([v for _, v in self._equity_history])
                # 计算日收益率
                daily_returns = equity_series.pct_change().dropna()
                
                if not daily_returns.empty:
                    # 年化波动率
                    volatility = daily_returns.std() * np.sqrt(252) * 100
                    
                    # 夏普比率 (假设无风险利率为 0)
                    mean_return = daily_returns.mean()
                    std_return = daily_returns.std()
                    if std_return > 0:
                        sharpe_ratio = (mean_return / std_return) * np.sqrt(252)
                    
                    # 索提诺比率
                    downside_returns = daily_returns[daily_returns < 0]
                    downside_std = downside_returns.std()
                    if downside_std > 0:
                        sortino_ratio = (mean_return / downside_std) * np.sqrt(252)
                    
                    # 卡玛比率
                    if max_drawdown > 0:
                        calmar_ratio = annual_return / max_drawdown
                        
            except Exception as e:
                print(f"[Metrics] 计算风险指标失败: {e}")

        # 计算平均每笔收益率
        avg_trade_return = 0.0
        if sell_trades:
            trade_returns = []
            for t in sell_trades:
                # 尝试获取 ROI
                roi = t.get('roi')
                if roi is not None:
                    trade_returns.append(roi)
                else:
                    # 尝试用盈亏和成本计算
                    pnl = t.get('profit_loss')
                    cost = t.get('cost') or (t.get('price', 0) * t.get('quantity', 0)) # 估算成本
                    if pnl is not None and cost and cost > 0:
                        trade_returns.append((pnl / cost) * 100)
            
            if trade_returns:
                avg_trade_return = sum(trade_returns) / len(trade_returns)
        
        # 计算最大连胜/连亏
        max_winning_streak = 0
        max_losing_streak = 0
        current_win = 0
        current_loss = 0
        
        for t in sell_trades:
            pnl = t.get('profit_loss', 0)
            if pnl > 0:
                current_win += 1
                current_loss = 0
                max_winning_streak = max(max_winning_streak, current_win)
            elif pnl < 0:
                current_loss += 1
                current_win = 0
                max_losing_streak = max(max_losing_streak, current_loss)

        # 【修复】先发送 final_metrics 事件，提供完整的指标数据给前端
        yield {
            "type": "final_metrics",
            "data": {
                "totalReturn": round(total_return, 2),
                "annualizedReturn": round(annual_return, 2), 
                "maxDrawdown": round(max_drawdown, 2),
                "sharpeRatio": round(sharpe_ratio, 2),
                "sortinoRatio": round(sortino_ratio, 2),
                "volatility": round(volatility, 2),
                "winRate": round(win_rate, 1),
                "profitFactor": round(profit_factor, 2),
                "tradesCount": trade_count,
                "avgTradeReturn": round(avg_trade_return, 2),
                "maxWinningStreak": max_winning_streak,
                "maxLosingStreak": max_losing_streak,
                "calmarRatio": round(calmar_ratio, 2)
            }
        }
        
        
        
        # 【数据持久化】将回测结果保存到数据库
        print("=" * 80)
        print("[DEBUG] 数据持久化代码开始执行...")
        print(f"[DEBUG] all_trades_log 长度: {len(all_trades_log)}")
        print("=" * 80)
        print("开始数据持久化...")
        import sqlite3
        
        try:
            # 获取策略名称
            strategy_name = getattr(strategy, 'strategy_name', strategy.__class__.__name__)
            
            # 连接数据库
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            # 准备回测结果数据
            start_date_str = start_ts.strftime("%Y-%m-%d")
            end_date_str = end_ts.strftime("%Y-%m-%d")
            db_total_return = (total_value - self.initial_capital) / self.initial_capital * 100
            
            # 简化处理：使用基本指标，其他指标设为0
            backtest_sql = """
                INSERT INTO backtest_results (
                    strategy_name, start_date, end_date, initial_capital, final_capital, 
                    total_return, annual_return, max_drawdown, sharpe_ratio, sortino_ratio, 
                    win_rate, profit_factor, trade_count, params
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 准备策略参数，使用递归序列化函数处理所有类型
            strategy_dict = getattr(strategy, '__dict__', {})
            serializable_params = {}
            for key, value in strategy_dict.items():
                try:
                    serialized_value = _make_json_serializable(value)
                    if serialized_value is not None:
                        serializable_params[key] = serialized_value
                except Exception:
                    pass
            
            # 准备回测结果参数
            backtest_params = (
                strategy_name,
                start_date_str,
                end_date_str,
                self.initial_capital,
                total_value,
                db_total_return,
                0.0,  # annual_return
                0.0,  # max_drawdown
                0.0,  # sharpe_ratio
                0.0,  # sortino_ratio
                0.0,  # win_rate
                0.0,  # profit_factor
                len(all_trades_log),
                json.dumps(serializable_params)
            )
            
            # 执行插入并获取回测ID
            cursor.execute(backtest_sql, backtest_params)
            backtest_id = cursor.lastrowid
            
            # 保存交易记录
            trade_sql = """
                INSERT INTO trade_records (
                    backtest_id, stock_code, stock_name, action, date, 
                    price, shares, amount, profit_loss
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 准备交易记录参数
            trade_params_list = []
            for trade in all_trades_log:
                amount = trade.get('cost', 0.0) if trade.get('action') == 'buy' else trade.get('revenue', 0.0)
                # 【修复】使用实际的 profit_loss，而不是硬编码 0.0
                profit_loss = trade.get('profit_loss', 0.0)
                trade_params = (
                    backtest_id,
                    trade.get('code', ''),
                    trade.get('code', ''),  # 暂时使用stock_code作为stock_name
                    trade.get('action', ''),
                    trade.get('date', ''),
                    trade.get('price', 0.0),
                    trade.get('shares', 0.0),
                    amount,
                    profit_loss  # 【修复】保存实际盈亏
                )
                trade_params_list.append(trade_params)
            
            # 批量插入交易记录
            if trade_params_list:
                cursor.executemany(trade_sql, trade_params_list)
            
            # 提交事务
            conn.commit()
            
            # 【新增】详细日志：确认数据库保存
            print("=" * 60)
            print("[OK] 回测结果已保存")
            print(f"   回测ID: {backtest_id}")
            print(f"   策略: {strategy_name}")
            print(f"   日期: {start_date_str} ~ {end_date_str}")
            print(f"   交易记录数: {len(trade_params_list)} 条")
            if trade_params_list:
                buy_count = sum(1 for t in all_trades_log if t.get('action') == 'buy')
                sell_count = sum(1 for t in all_trades_log if t.get('action') == 'sell')
                print(f"   买入: {buy_count} 笔 | 卖出: {sell_count} 笔")
                # 显示前3笔交易作为验证
                print(f"   前3笔交易:")
                for i, trade in enumerate(all_trades_log[:3], 1):
                    action_cn = "买入" if trade.get('action') == 'buy' else "卖出"
                    print(f"     {i}. [{trade.get('date')}] {action_cn} {trade.get('code')}: "
                               f"{trade.get('shares')}股 @ {trade.get('price'):.2f}")
            else:
                print(f"   [WARN] 本次回测没有产生任何交易记录")
                print(f"   可能原因: 策略未生成信号 / 所有信号被过滤 / 资金不足")
            print("=" * 60)
            
            # 关闭连接
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] 数据持久化失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 产出最终结果
        # 【修复】转换交易记录字段名以匹配前端期望
        frontend_trades = []
        for trade in all_trades_log:
            # 【Bug修复】确保股票代码补齐到6位，避免00开头股票丢失前导零
            stock_code = str(trade.get('code', ''))
            padded_code = stock_code.zfill(6) if stock_code.isdigit() else stock_code
            
            frontend_trade = {
                "id": f"{trade.get('date', '')}_{padded_code}_{trade.get('action', '')}",
                "date": trade.get('date', ''),
                "symbol": padded_code,  # 前端显示用
                "symbolCode": padded_code,  # 前端期望的字段名
                "code": padded_code,  # 保留原字段
                "action": trade.get('action', ''),
                "price": trade.get('price', 0.0),
                "quantity": trade.get('shares', 0),  # 前端期望 quantity
                "shares": trade.get('shares', 0),  # 保留原字段
                "commission": trade.get('commission', 0.0),
                "cost": trade.get('cost', 0.0),
                "revenue": trade.get('revenue', 0.0),
                "profitLoss": trade.get('profit_loss', 0.0),  # 前端期望 profitLoss (驼峰)
                "profit_loss": trade.get('profit_loss', 0.0),  # 保留原字段
                "roi": trade.get('roi', 0.0),
                "entry_price": trade.get('entry_price', 0.0),  # 开仓价
                "holdingDays": trade.get('holding_days', 0)  # 持有天数
            }
            frontend_trades.append(frontend_trade)
        
        yield {
            "type": "stream_complete",
            "data": {
                "finalEquity": total_value,
                "totalReturn": round((total_value - self.initial_capital) / self.initial_capital * 100, 2),
                "totalTrades": trade_count,
                "winRate": round(win_rate, 1),
                "profitFactor": round(profit_factor, 2),
                "equityCurve": equity_curve_data,
                "trades": frontend_trades  # 使用转换后的交易记录
            }
        }
        
        # 【DEBUG】确认 trades 数据
        print(f"[DEBUG] stream_complete 事件包含 {len(frontend_trades)} 条交易记录")
        if frontend_trades:
            print(f"[DEBUG] 第一条交易: {frontend_trades[0]}")

    
    def _normalize_datetime(
        self, 
        dt: Union[str, pd.Timestamp, datetime]
    ) -> pd.Timestamp:
        """统一转换为 pd.Timestamp"""
        if isinstance(dt, str):
            return pd.to_datetime(dt)
        elif isinstance(dt, datetime):
            return pd.Timestamp(dt)
        elif isinstance(dt, pd.Timestamp):
            return dt
        else:
            raise TypeError(f"不支持的时间类型: {type(dt)}")
    
    def _get_time_series(
        self,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp
    ) -> List[pd.Timestamp]:
        """
        根据时间粒度获取时间序列
        
        返回：
            List[pd.Timestamp]
        """
        if self.time_granularity == 'daily':
            # 日线：获取交易日
            try:
                trading_dates = self.data_query.get_trading_dates(
                    start_ts.strftime("%Y-%m-%d"),
                    end_ts.strftime("%Y-%m-%d")
                )
                return [pd.to_datetime(d) for d in trading_dates]
            except Exception as e:
                print(f"获取交易日失败: {e}")
                return []
        
        elif self.time_granularity == 'minute':
            # 分钟线：生成交易时间（9:30-11:30, 13:00-15:00）
            time_series = []
            current = start_ts.replace(hour=9, minute=30, second=0, microsecond=0)
            
            while current <= end_ts:
                # 上午：9:30-11:30
                morning_start = current.replace(hour=9, minute=30)
                morning_end = current.replace(hour=11, minute=30)
                
                # 下午：13:00-15:00
                afternoon_start = current.replace(hour=13, minute=0)
                afternoon_end = current.replace(hour=15, minute=0)
                
                # 生成分钟序列
                for period_start, period_end in [
                    (morning_start, morning_end),
                    (afternoon_start, afternoon_end)
                ]:
                    t = period_start
                    while t <= period_end and t <= end_ts:
                        time_series.append(t)
                        t += timedelta(minutes=1)
                
                current += timedelta(days=1)
            
            return time_series
        
        elif self.time_granularity == 'tick':
            # Tick级别：需要从数据库读取实际tick数据
            # 这里简化处理，实际应该查询tick表
            raise NotImplementedError("Tick级别回测需要实现tick数据查询")
        
        else:
            raise ValueError(f"不支持的时间粒度: {self.time_granularity}")
    
    def _get_stock_pool_at_time(self, date: Union[str, pd.Timestamp], data_query) -> pd.DataFrame:
        """
        获取指定日期的股票池
        
        参数：
            date: 日期（支持 str 或 pd.Timestamp）
            data_query: 数据查询对象
        
        优化策略：使用 LRU 缓存 + DuckDB 批量查询
        关键变更：从单条 SQL 改为范围查询，大幅降低数据库连接开销
        """
        # 转换为字符串格式
        if isinstance(date, pd.Timestamp):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = str(date)
        
        # 1. 尝试从缓存获取
        if date_str in self._stock_pool_cache:
            # 更新LRU访问顺序：将该键移到列表末尾
            self._cache_order.remove(date_str)
            self._cache_order.append(date_str)
            return self._stock_pool_cache[date_str]
        
        # 2. 缓存未命中，从数据库加载
        start_time = time.perf_counter()
        
        try:
            # 使用duckdb进行范围查询
            result = data_query.get_stock_pool(date_str)
            query_time = time.perf_counter() - start_time
            
            # 3. 缓存结果并检查LRU淘汰
            self._stock_pool_cache[date_str] = result
            self._cache_order.append(date_str)
            
            # LRU淘汰逻辑：超过阈值则剔除最早访问的条目
            if len(self._stock_pool_cache) > self._cache_max_size:
                if self._cache_order:
                    oldest_key = self._cache_order.pop(0)
                    removed = self._stock_pool_cache.pop(oldest_key, None)
                    print(f"[LRU Eviction] 缓存已满，剔除最旧条目: {oldest_key} (当前缓存大小: {len(self._stock_pool_cache)})")
            
            # 记录查询耗时
            self._last_query_time = query_time
            
        except Exception as e:
            print(f"获取股票池失败 {date_str}: {e}")
            result = pd.DataFrame()
        
        return result
    
    def _execute_trades(
        self,
        current_time: pd.Timestamp,
        stock_pool: Any,  # pd.DataFrame or pl.DataFrame
        signals: Dict[str, str],
        portfolio: Dict[str, int],
        cash: float,
        position_info: Optional[Dict[str, Dict[str, Any]]] = None,  # NEW: Track cost and entry_date
        strategy: Optional[Any] = None  # NEW: Strategy instance for position management
    ) -> tuple:
        """
        执行交易（高性能版：集成 Polars 加速与真实交易规则）
        """
        # Initialize position_info if not provided
        if position_info is None:
            position_info = {}
        else:
            position_info = position_info.copy()
        
        trades = []
        new_portfolio = portfolio.copy()
        new_cash = cash
        date_str = current_time.strftime("%Y-%m-%d")

        # 【核心修复】支持策略层自定义手续费/零摩擦
        # 优先级：策略实例属性 > 引擎实例属性
        commission_rate = getattr(strategy, 'commission_rate', self.commission_rate)
        min_commission = getattr(strategy, 'min_commission', self.min_commission)
        sell_tax = getattr(strategy, 'sell_tax', getattr(self, 'sell_tax', 0.001))

        # 【性能优化】只处理有信号的股票
        # 使用 isin 过滤后再 to_dict，避免处理整个 DataFrame
        
        # 1. 快速检查：如果没有信号，直接返回
        if not signals:
            return new_portfolio, new_cash, trades, position_info
        
        # 2. 只提取有信号的股票数据
        signal_codes = set(signals.keys())
        if isinstance(stock_pool, pd.DataFrame):
            if 'stock_code' in stock_pool.columns:
                # 过滤出有信号的股票
                signal_pool = stock_pool[stock_pool['stock_code'].isin(signal_codes)]
                # 转换为字典（只有几十行，很快）
                if len(signal_pool) > 0:
                    signal_data = signal_pool.set_index('stock_code').to_dict('index')
                else:
                    signal_data = {}
            else:
                signal_data = {}
        else:
            # Polars 路径
            stock_pool_pd = stock_pool.to_pandas()
            if 'stock_code' in stock_pool_pd.columns:
                signal_pool = stock_pool_pd[stock_pool_pd['stock_code'].isin(signal_codes)]
                if len(signal_pool) > 0:
                    signal_data = signal_pool.set_index('stock_code').to_dict('index')
                else:
                    signal_data = {}
            else:
                signal_data = {}

        # 3. 【交易循环】分两阶段执行：先卖后买
        # 阶段1：处理所有卖出信号，更新现金
        for code, signal in signals.items():
            # 获取信号类型（兼容字符串格式或字典格式）
            sig_type = signal.get('action') if isinstance(signal, dict) else signal
            if sig_type not in ('sell', 'exit'):
                continue  # 跳过非卖出信号
            
            # 检查是否持有该股票
            current_position = new_portfolio.get(code, 0)
            if current_position <= 0:
                continue  # 没有持仓，跳过
            
            # 从 signal_data 中查询
            if code not in signal_data:
                continue
            
            data = signal_data[code]
            # 【价格策略切换】按用户要求：使用开盘价 (open) 作为 T+1 执行价
            price = float(data.get('open', 0))
            is_suspended = bool(data.get('is_suspended', 0))
            is_limit_down = bool(data.get('is_limit_down', 0))
            
            # 基础过滤：价格异常或停牌
            if price <= 0 or is_suspended:
                from config.logger import get_logger
                get_logger(__name__).warning(f"[交易拦截] {code} 无法卖出: {'停牌' if is_suspended else '价格异常'}")
                continue
            
            # 跌停不能卖出
            if is_limit_down:
                from config.logger import get_logger
                get_logger(__name__).warning(f"[交易拦截] {code} 无法卖出: 跌停")
                continue
            
            # 执行卖出
            revenue = current_position * price
            commission = max(revenue * commission_rate, min_commission)
            tax = revenue * sell_tax
            net_revenue = revenue - commission - tax
            
            # 计算盈亏
            pos_data = position_info.get(code, {})
            avg_cost_per_share = pos_data.get('cost', price)
            entry_date = pos_data.get('entry_date', date_str)
            cost_basis = avg_cost_per_share * current_position
            profit_loss = net_revenue - cost_basis
            roi = (profit_loss / cost_basis * 100) if cost_basis > 0 else 0
            
            # 计算持有天数
            try:
                from datetime import datetime
                d1 = datetime.strptime(entry_date, "%Y-%m-%d")
                d2 = datetime.strptime(date_str, "%Y-%m-%d")
                holding_days = (d2 - d1).days
            except:
                holding_days = 0

            new_cash += net_revenue
            del new_portfolio[code]
            
            if code in position_info:
                del position_info[code]
            
            trades.append({
                "date": date_str,
                "code": code,
                "action": "sell",
                "shares": current_position,
                "price": price,
                "revenue": net_revenue,
                "commission": commission,
                "tax": tax,
                "profit_loss": profit_loss,
                "roi": roi,
                "entry_price": avg_cost_per_share,
                "entry_date": entry_date,
                "holding_days": holding_days,
                "indicators": signal.get('indicators', {}) if isinstance(signal, dict) else {}
            })
        
        # 阶段2：处理所有买入信号（使用更新后的现金）
        # 【仓位管理修复】先检查策略的仓位限制
        strategy_max_positions = getattr(strategy, 'max_positions', None) if strategy is not None else None
        strategy_position_ratio = getattr(strategy, 'position_ratio', None) if strategy is not None else None
        
        # 计算buy信号数量和当前持仓数
        buy_signals = {code: sig for code, sig in signals.items() 
                      if (sig.get('action') if isinstance(sig, dict) else sig) in ('buy', 'enter')}
        current_positions_count = len(new_portfolio)
        
        # 如果策略定义了最大持仓数，检查是否还能买入
        can_buy_count = len(buy_signals)  # 默认可以买所有信号
        if strategy_max_positions is not None and current_positions_count >= strategy_max_positions:
            # 已达到最大持仓，不能再买入
            buy_signals = {}
        elif strategy_max_positions is not None:
            # 限制买入数量，不超过最大持仓数
            can_buy_count = min(can_buy_count, strategy_max_positions - current_positions_count)
        
        # 如果有买入限制，只处理前N个信号
        if can_buy_count < len(buy_signals):
            buy_signals = dict(list(buy_signals.items())[:can_buy_count])
        
        for code, signal in buy_signals.items():
            # 检查是否已持有
            current_position = new_portfolio.get(code, 0)
            if current_position > 0:
                continue  # 已有持仓，跳过
            
            # 从 signal_data 中查询
            if code not in signal_data:
                continue
            
            data = signal_data[code]
            # 【价格策略切换】按用户要求：使用开盘价 (open) 作为 T+1 执行价
            price = float(data.get('open', 0))
            is_suspended = bool(data.get('is_suspended', 0))
            is_limit_up = bool(data.get('is_limit_up', 0))
            
            # 基础过滤：价格异常或停牌
            if price <= 0 or is_suspended:
                from config.logger import get_logger
                get_logger(__name__).warning(f"[交易拦截] {code} 无法买入: {'停牌' if is_suspended else '价格异常或缺失数据'}")
                continue
            
            # 涨停不能买入
            if is_limit_up:
                from config.logger import get_logger
                get_logger(__name__).warning(f"[交易拦截] {code} 无法买入: 涨停")
                continue
            
            # 【复利开启】使用当前可用现金 (new_cash) 而非固定的初始资金
            if strategy_position_ratio is not None:
                # 策略定义了仓位比例，基于当前现金计算
                target_investment = new_cash * strategy_position_ratio
            else:
                # 回退到默认10%（基于当前现金）
                target_investment = new_cash * 0.1
            
            if target_investment > new_cash:
                target_investment = new_cash  # 移除 5% 缓冲，允许全仓买入
            
            if target_investment <= 1000:  # 资金过少不买入
                continue
            
            # 计算股数（需符合一手100股规则）
            shares = int(target_investment / (price * (1 + commission_rate)))
            shares = (shares // 100) * 100
            
            if shares >= 100:
                cost = shares * price
                commission = max(cost * commission_rate, min_commission)
                total_outlay = cost + commission
                
                if total_outlay <= new_cash:
                    new_portfolio[code] = shares
                    new_cash -= total_outlay
                    
                    # 记录成本基础和入场日期
                    position_info[code] = {
                        'cost': total_outlay / shares,
                        'entry_date': date_str
                    }
                    
                    trades.append({
                        "date": date_str,
                        "code": code,
                        "action": "buy",
                        "shares": shares,
                        "price": price,
                        "cost": total_outlay,
                        "commission": commission,
                        "holding_days": 0,  # Buy trades have 0 holding days (entry point)
                        "indicators": signal.get('indicators', {}) if isinstance(signal, dict) else {}
                    })

        return new_portfolio, new_cash, trades, position_info
  # Return position_costs

    
    def _calculate_portfolio_value(
        self,
        date: pd.Timestamp,
        positions: Dict[str, float],
        stock_pool: Any = None,
        use_pl: bool = False,
        data_dict: Dict[str, Any] = None
    ) -> float:
        """
        计算投资组合价值（性能优化版）
        """
        if not positions:
            return 0.0
        
        total_value = 0.0
        
        # 【性能优化】优先使用 pre-calculated data_dict
        if data_dict:
            for code, shares in positions.items():
                if code in data_dict:
                    # 使用 Raw Price (close) 计算市值
                    price = data_dict[code].get('close', 0)
                    total_value += float(price) * shares
            return total_value

        # 如果没有 data_dict，退回到原有逻辑
        if use_pl and stock_pool is not None:
            import polars as pl
            for code, shares in positions.items():
                try:
                    price_data = stock_pool.filter(pl.col('stock_code') == code).select('close')
                    if not price_data.is_empty():
                        price = price_data.item()
                        total_value += float(price) * shares
                except:
                    continue
        elif stock_pool is not None:
            # Pandas 路径
            if 'stock_code' in stock_pool.columns:
                stock_pool = stock_pool.set_index('stock_code')
            
            for code, shares in positions.items():
                if code in stock_pool.index:
                    price = stock_pool.loc[code, 'close']
                    total_value += float(price) * shares
        
        return total_value

    @staticmethod
    @njit(cache=True)
    def _calc_value_inner_numba(shares_arr: np.ndarray, prices_arr: np.ndarray) -> float:
        """Numba 加速的核心计算循环"""
        return np.sum(shares_arr * prices_arr)

    def _calc_value_numba(self, positions: Dict[str, float], price_map: Dict[str, float]) -> float:
        """将 Python 字典转换为 NumPy 数组并调用 Numba 内核"""
        shares_list = []
        prices_list = []
        for code, shares in positions.items():
            price = price_map.get(code, 0)
            if price > 0:
                shares_list.append(shares)
                prices_list.append(price)
        
        if not shares_list:
            return 0.0
            
        return self._calc_value_inner_numba(
            np.array(shares_list, dtype=np.float64),
            np.array(prices_list, dtype=np.float64)
        )

    def _get_update_frequency(self) -> int:
        """获取更新频率（用于非日线粒度）"""
        if self.time_granularity == 'daily':
            return 1
        elif self.time_granularity == 'minute':
            return 60  # 每60分钟更新一次
        else:
            return 1