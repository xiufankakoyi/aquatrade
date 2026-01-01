# backtest/optimized_backtest_engine.py
"""
优化的回测引擎 - Polars + CuPy + Numba 架构

架构说明：
1. 数据加载：使用 Polars 加载 Parquet，立即转换为 NumPy 数组
2. 指标计算：在 GPU (CuPy) 上计算技术指标，然后移回 CPU
3. 执行循环：使用 Numba JIT 编译的快速循环函数
4. 策略接口：保持与现有策略接口兼容

性能优化：
- GPU 加速的指标计算
- Numba JIT 编译的执行循环
- 向量化的数据处理
"""
import numpy as np
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    cp = None

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import numba
    from numba import jit, types, int64
    from numba.typed import List
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    numba = None
    jit = lambda *args, **kwargs: lambda f: f
    int64 = None
    List = None

import pandas as pd
from tqdm import tqdm
from typing import Dict, Any, Generator, Tuple, List, Optional
from threading import Event
import time
import os
from pathlib import Path
import hashlib


class OptimizedBacktestEngine:
    """优化的回测引擎 - Polars + CuPy + Numba 架构"""
    
    # 默认配置常量
    DEFAULT_INITIAL_CAPITAL = 1_000_000
    DEFAULT_COMMISSION_RATE = 0.0005
    DEFAULT_MIN_COMMISSION = 5.0
    DEFAULT_SELL_TAX = 0.001
    DEFAULT_BOARD_LOT = 100
    DEFAULT_MAX_POSITIONS = 3
    DEFAULT_POSITION_RATIO = 0.2
    
    # 预加载配置：动态窗口设置 (The "N+M" Rule)
    # 预加载天数 = Max(技术指标最大窗口) + 冗余安全边际
    # 5日均线：理论最小预加载为5个交易日
    # 前置图形（如杯柄形态、底部结构）：通常需要20-60个交易日
    # 推荐配置：60个交易日（覆盖大部分技术指标和形态识别）
    DEFAULT_WARMUP_DAYS = 60  # 默认预热天数（交易日，非自然日）
    
    def __init__(self, data_query, initial_capital=None, commission_rate=None):
        self.data_query = data_query
        
        # 初始化资金和费率
        if initial_capital is None:
            env_capital = os.getenv('INITIAL_CAPITAL')
            self.initial_capital = float(env_capital) if env_capital else self.DEFAULT_INITIAL_CAPITAL
        else:
            self.initial_capital = initial_capital
            
        if commission_rate is None:
            env_rate = os.getenv('COMMISSION_RATE')
            self.commission_rate = float(env_rate) if env_rate else self.DEFAULT_COMMISSION_RATE
        else:
            self.commission_rate = commission_rate
        
        # 检查依赖
        if not POLARS_AVAILABLE:
            raise ImportError("Polars is required. Install with: pip install polars")
        if not NUMBA_AVAILABLE:
            raise ImportError("Numba is required. Install with: pip install numba")
        
        # 过滤统计
        self._filter_stats = {
            'limit_up_blocked': 0,
            'limit_down_blocked': 0,
            'suspended_blocked': 0,
            'total_blocked': 0
        }

    def _validate_dates(self, start_date, end_date) -> Tuple[str, str]:
        """确保日期是字符串格式"""
        start_date_str = start_date
        end_date_str = end_date
        if isinstance(start_date, pd.Timestamp):
            start_date_str = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, pd.Timestamp):
            end_date_str = end_date.strftime('%Y-%m-%d')
        return start_date_str, end_date_str
    
    def _convert_to_matrix_fast(self, df: pd.DataFrame, dates: List[str], stock_codes: List[str]) -> np.ndarray:
        """
        极速矩阵转换：Pandas -> NumPy (0.5s within 800k rows)
        
        参数:
            df: Pandas DataFrame，包含 trade_date, stock_code, open, high, low, close
            dates: 排序后的交易日期列表
            stock_codes: 排序后的股票代码列表
        
        返回:
            price_matrix: (T, N, 4) - [open, high, low, close] for each time and stock
        """
        import time
        from config.logger import get_logger
        logger = get_logger(__name__)
        
        t0 = time.perf_counter()
        
        # 1. 确保数据有序
        df['trade_date'] = pd.Categorical(df['trade_date'], categories=dates, ordered=True)
        df['stock_code'] = pd.Categorical(df['stock_code'], categories=stock_codes, ordered=True)
        
        # 2. 获取整数索引 (int32)
        # .cat.codes 非常快，这是底层 C 实现的
        i_row = df['trade_date'].cat.codes.values
        j_col = df['stock_code'].cat.codes.values
        
        # 3. 过滤无效数据 (-1)
        mask = (i_row >= 0) & (j_col >= 0)
        i_row = i_row[mask]
        j_col = j_col[mask]
        
        # 4. 初始化矩阵
        T = len(dates)
        N = len(stock_codes)
        # 使用 float32 节省内存并加速
        price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
        
        # 5. 向量化填充 (Fancy Indexing)
        # 一次性赋值，不要循环！
        vals_open = df.loc[mask, 'open'].values.astype(np.float32)
        vals_high = df.loc[mask, 'high'].values.astype(np.float32)
        vals_low = df.loc[mask, 'low'].values.astype(np.float32)
        vals_close = df.loc[mask, 'close'].values.astype(np.float32)
        
        price_matrix[i_row, j_col, 0] = vals_open
        price_matrix[i_row, j_col, 1] = vals_high
        price_matrix[i_row, j_col, 2] = vals_low
        price_matrix[i_row, j_col, 3] = vals_close
        
        # 【关键】强制转换为 C-连续内存，供 Numba 使用
        price_matrix = np.ascontiguousarray(price_matrix, dtype=np.float32)
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[Perf] 矩阵构建耗时: {elapsed_ms:.2f}ms")
        return price_matrix
    
    def _get_cache_path(self, start_date: str, end_date: str) -> Tuple[str, str]:
        """
        生成唯一的缓存文件路径
        
        参数:
            start_date: 起始日期
            end_date: 结束日期
        
        返回:
            (cache_path_matrix, cache_path_meta) - 矩阵缓存路径和元数据缓存路径
        """
        # 确保缓存目录存在
        cache_dir = "./cache/matrices"
        os.makedirs(cache_dir, exist_ok=True)
        
        # 根据日期生成指纹（使用哈希避免文件名过长）
        fingerprint_str = f"{start_date}_{end_date}"
        fingerprint = hashlib.md5(fingerprint_str.encode()).hexdigest()[:16]
        
        cache_path_matrix = os.path.join(cache_dir, f"price_matrix_{fingerprint}.npy")
        cache_path_meta = os.path.join(cache_dir, f"meta_{fingerprint}.npy")
        
        return cache_path_matrix, cache_path_meta

    def _load_data_with_polars_streaming(self, start_date: str, end_date: str, 
                                         required_warmup: int = 60) -> Generator:
        """
        流式加载数据（生成器版本），在关键步骤之间 yield 进度更新，避免30秒超时
        
        Yields:
            - 进度更新字典（type="initializing"）
            - 最终结果元组 (price_matrix, stock_codes, trading_dates)
        """
        from config.logger import get_logger
        import time
        logger = get_logger(__name__)
        
        _t_method_start = time.perf_counter()
        logger.debug(f"开始加载数据: {start_date} 到 {end_date}, warmup={required_warmup}")
        
        # =====================================================================
        # 【缓存检查】检查是否存在磁盘缓存（NumPy mmap 方案）
        # =====================================================================
        cache_path_matrix, cache_path_meta = self._get_cache_path(start_date, end_date)
        
        if os.path.exists(cache_path_matrix) and os.path.exists(cache_path_meta):
            logger.info(f"⚡ 命中磁盘矩阵缓存，跳过 LanceDB 加载...")
            
            yield {
                "type": "initializing",
                "data": {"message": "正在从磁盘缓存加载矩阵...", "progress": 5}
            }
            
            try:
                # 【省内存关键】mmap_mode='r' 
                # 这不会把文件读入内存，而是让操作系统按需加载，内存占用极低
                _t_cache_load = time.perf_counter()
                price_matrix = np.load(cache_path_matrix, mmap_mode='r')
                
                # 加载元数据 (stock_codes, dates)
                meta = np.load(cache_path_meta, allow_pickle=True).item()
                stock_codes = meta['stock_codes']
                trading_dates = meta['trading_dates']
                
                _t_cache_load_end = time.perf_counter()
                cache_load_time = (_t_cache_load_end - _t_cache_load) * 1000
                logger.info(f"✓ 缓存加载完成: {cache_load_time:.2f}ms (大小: {price_matrix.nbytes / 1024 / 1024:.2f} MB)")
                
                # 因为是 mmap，这里我们需要转为内存连续数组给 Numba (如果内存够，就 copy 一次；不够就直接传)
                # 对于 13MB 的数据，直接 np.array(price_matrix) 加载进内存完全没问题
                yield {
                    "type": "initializing",
                    "data": {"message": "正在转换矩阵格式...", "progress": 10}
                }
                
                _t_convert = time.perf_counter()
                # 转换为 C-连续内存数组（供 Numba 使用）
                price_matrix = np.ascontiguousarray(price_matrix, dtype=np.float32)
                _t_convert_end = time.perf_counter()
                convert_time = (_t_convert_end - _t_convert) * 1000
                logger.info(f"✓ 矩阵转换完成: {convert_time:.2f}ms")
                
                # 预加载股票池数据（即使使用缓存，也需要预加载股票池数据）
                yield {
                    "type": "initializing",
                    "data": {"message": "正在预加载股票池数据...", "progress": 33}
                }
                
                # 计算加载日期范围（用于预加载股票池数据）
                safe_margin_days = required_warmup * 2
                earliest_date = pd.to_datetime(start_date) - pd.Timedelta(days=safe_margin_days)
                earliest_date_str = earliest_date.strftime('%Y-%m-%d')
                warmup_trading_dates = self.data_query.get_trading_dates(earliest_date_str, start_date)
                if warmup_trading_dates and len(warmup_trading_dates) >= required_warmup:
                    load_start_str = warmup_trading_dates[-required_warmup]
                else:
                    load_start_str = earliest_date_str
                
                if hasattr(self.data_query, 'preload_backtest_data'):
                    try:
                        self.data_query.preload_backtest_data(load_start_str, end_date)
                        logger.info(f"✓ 股票池数据预加载完成")
                    except Exception as e:
                        logger.error(f"预加载股票池数据失败: {e}", exc_info=True)
                
                # 预加载涨跌停数据
                yield {
                    "type": "initializing",
                    "data": {"message": "正在预加载涨跌停数据...", "progress": 35}
                }
                
                if hasattr(self.data_query, 'preload_stock_limit_status'):
                    try:
                        self.data_query.preload_stock_limit_status(start_date, end_date)
                        logger.info(f"✓ 涨跌停数据预加载完成")
                    except Exception as e:
                        logger.error(f"预加载涨跌停数据失败: {e}", exc_info=True)
                
                # 返回缓存的结果
                yield (price_matrix, stock_codes, trading_dates)
                return
                
            except Exception as e:
                logger.warning(f"缓存加载失败，回退到正常加载: {e}", exc_info=True)
                # 继续执行正常加载流程
        
        # ================= 缓存未命中，执行原有加载逻辑 =================
        
        _progress_update_1 = {
            "type": "initializing",
            "data": {"message": "正在从数据库加载数据...", "progress": 5}
        }
        yield _progress_update_1
        
        # 计算加载日期范围（包含预热期）
        _t_calc_range = time.perf_counter()
        
        # 【关键修复】"起始点隔离"机制 (Start Date Offset) - 按交易日历计算
        # 按交易日历计算 warmup，而非自然日（避免停牌导致的有效 Bar 数量不足）
        safe_margin_days = required_warmup * 2
        earliest_date = pd.to_datetime(start_date) - pd.Timedelta(days=safe_margin_days)
        earliest_date_str = earliest_date.strftime('%Y-%m-%d')
        
        # 获取从 earliest_date 到 start_date 的所有交易日
        warmup_trading_dates = self.data_query.get_trading_dates(earliest_date_str, start_date)
        if not warmup_trading_dates:
            # 如果获取失败，回退到自然日计算
            logger.warning(f"无法获取交易日历，回退到自然日计算 warmup")
            load_start = pd.to_datetime(start_date) - pd.Timedelta(days=required_warmup)
            load_start_str = load_start.strftime('%Y-%m-%d')
        else:
            # 取前 required_warmup 个交易日（如果不足，则使用所有可用交易日）
            if len(warmup_trading_dates) >= required_warmup:
                # 取前 required_warmup 个，第一个就是预加载起始日期
                load_start_str = warmup_trading_dates[-required_warmup]
            else:
                # 如果交易日不足，使用最早可用的日期
                logger.warning(f"交易日不足 {required_warmup} 天（实际 {len(warmup_trading_dates)} 天），使用最早可用日期")
                load_start_str = warmup_trading_dates[0] if warmup_trading_dates else earliest_date_str
        
        _t_calc_range_end = time.perf_counter()
        logger.debug(f"日期范围计算完成: {load_start_str}, 耗时 {_t_calc_range_end - _t_calc_range:.3f}s")
        
        # 获取交易日期
        _t_get_dates = time.perf_counter()
        trading_dates = self.data_query.get_trading_dates(start_date, end_date)
        _t_get_dates_end = time.perf_counter()
        logger.debug(f"获取交易日期完成: {len(trading_dates) if trading_dates else 0} 个日期, 耗时 {_t_get_dates_end - _t_get_dates:.3f}s")
        if not trading_dates:
            raise ValueError(f"No trading dates found between {start_date} and {end_date}")
        
        logger.info(f"加载数据: {load_start_str} 到 {end_date} (回测: {start_date} 到 {end_date})")
        
        _progress_update_2 = {
            "type": "initializing",
            "data": {"message": "正在从 LanceDB 加载行情数据...", "progress": 10}
        }
        yield _progress_update_2
        
        # 检查是否使用 LanceDB
        _t_check_lancedb = time.perf_counter()
        use_lancedb = hasattr(self.data_query, '_use_lancedb') and self.data_query._use_lancedb
        _t_check_lancedb_end = time.perf_counter()
        logger.debug(f"LanceDB 检查完成: use_lancedb={use_lancedb}, 耗时 {_t_check_lancedb_end - _t_check_lancedb:.3f}s")
        
        if use_lancedb and hasattr(self.data_query, 'lance_manager'):
            try:
                # 跳过股票池过滤（避免额外的 get_stock_pool 调用，可能导致卡顿）
                # 直接加载所有股票，然后在内存中过滤
                stock_codes_filter = None
                
                _progress_update_3 = {
                    "type": "initializing",
                    "data": {"message": "正在从 LanceDB 查询数据...", "progress": 15}
                }
                yield _progress_update_3
                
                # 加载数据（不传 stock_codes_filter，加载所有股票）
                _t_load_lazy = time.perf_counter()
                lazy_df = self.data_query.lance_manager.load_to_polars_lazy(
                    start_date=load_start_str,
                    end_date=end_date,
                    stock_codes=None,  # 不传股票池过滤，避免额外的查询
                    columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
                )
                _t_load_lazy_end = time.perf_counter()
                logger.debug(f"load_to_polars_lazy 完成，耗时 {_t_load_lazy_end - _t_load_lazy:.3f}s")
                
                _progress_update_4 = {
                    "type": "initializing",
                    "data": {"message": "正在执行数据库查询...", "progress": 18}
                }
                yield _progress_update_4
                
                _t_collect = time.perf_counter()
                df = lazy_df.collect()
                _t_collect_end = time.perf_counter()
                logger.debug(f"collect 完成，耗时 {_t_collect_end - _t_collect:.3f}s, 行数: {len(df) if not df.is_empty() else 0}")
                
                if df.is_empty():
                    raise ValueError("No data loaded from LanceDB")
            except Exception as e:
                logger.warning(f"LanceDB 加载失败，回退到 DuckDB: {e}")
                use_lancedb = False
        
        if not use_lancedb:
            # DuckDB 批量查询
            all_trading_dates = self.data_query.get_trading_dates(load_start_str, end_date)
            logger.info(f"使用批量查询加载数据: {load_start_str} 到 {end_date} ({len(all_trading_dates)} 个交易日)")
            
            yield {
                "type": "initializing",
                "data": {"message": "正在从 DuckDB 批量查询数据...", "progress": 15}
            }
            
            try:
                if hasattr(self.data_query, '_get_stock_pool_batch'):
                    df_pd = self.data_query._get_stock_pool_batch(all_trading_dates)
                else:
                    placeholders = ",".join(["?"] * len(all_trading_dates))
                    query = f"""
                        SELECT stock_code, trade_date, open, high, low, close, volume
                        FROM stock_daily
                        WHERE trade_date IN ({placeholders})
                        ORDER BY trade_date, stock_code
                    """
                    df_pd = self.data_query._query_df(query, params=all_trading_dates)
                
                if df_pd is None or df_pd.empty:
                    raise ValueError("No data loaded from batch query")
                
                df = pl.from_pandas(df_pd).lazy().select([
                    'stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume'
                ]).collect()
            except Exception as e:
                logger.warning(f"批量查询失败: {e}")
                raise
        
        # ==============================================================================
        # 【第三阶段优化】全局唯一的代码序列：锁定股票代码列表，确保所有矩阵对齐
        # 使用 sorted() 确保顺序一致，避免"张冠李戴"的数据对齐错误
        # ==============================================================================
        stock_codes = sorted(df['stock_code'].unique().to_list())
        dates = sorted(df['trade_date'].unique().to_list())
        
        # 锁定全局股票代码列表（不可变）
        # 后续所有矩阵（price_matrix, signal_matrix）必须严格按此顺序对齐
        GLOBAL_STOCK_LIST = tuple(stock_codes)  # 使用 tuple 确保不可变
        logger.info(f"[DATA] 锁定全局股票代码序列: {len(GLOBAL_STOCK_LIST)} 只股票")
        # ==============================================================================
        
        yield {
            "type": "initializing",
            "data": {"message": f"正在构建价格矩阵 ({len(dates)} 个交易日, {len(stock_codes)} 只股票)...", "progress": 20}
        }
        
        # 创建价格矩阵
        T = len(dates)
        N = len(stock_codes)
        
        # 【性能优化】使用极速矩阵转换方法（Categorical + NumPy 直接赋值）
        try:
            # 转换为 Pandas（如果 df 是 Polars）
            if hasattr(df, 'to_pandas'):
                df_pd = df.to_pandas()
            else:
                df_pd = df
            
            # 确保 dates 和 stock_codes 是排序的
            dates_sorted = sorted(dates)
            stock_codes_sorted = sorted(stock_codes)
            
            # 使用极速矩阵转换方法
            price_matrix = self._convert_to_matrix_fast(df_pd, dates_sorted, stock_codes_sorted)
            
            logger.info(f"✓ 价格矩阵构建完成（极速方法）: {T} 个交易日, {N} 只股票")
            
        except Exception as e:
            # 回退到原始方法（如果向量化失败）
            logger.warning(f"极速矩阵构建失败，回退到循环方法: {e}", exc_info=True)
            price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
            
            # 原始循环方法（作为回退）
            for t, date in enumerate(dates):
                if t > 0 and t % max(1, T // 10) == 0:  # 每10%发送一次进度
                    progress = 20 + int((t / T) * 15)  # 20% -> 35%
                    yield {
                        "type": "initializing",
                        "data": {"message": f"正在填充价格矩阵 ({t}/{T})...", "progress": progress}
                    }
                
                date_df = df.filter(pl.col('trade_date') == date)
                for n, code in enumerate(stock_codes):
                    code_row = date_df.filter(pl.col('stock_code') == code)
                    if not code_row.is_empty():
                        try:
                            row_dict = code_row.to_dicts()[0]
                            price_matrix[t, n, 0] = row_dict.get('open', np.nan) if 'open' in row_dict else np.nan
                            price_matrix[t, n, 1] = row_dict.get('high', np.nan) if 'high' in row_dict else np.nan
                            price_matrix[t, n, 2] = row_dict.get('low', np.nan) if 'low' in row_dict else np.nan
                            price_matrix[t, n, 3] = row_dict.get('close', np.nan) if 'close' in row_dict else np.nan
                        except Exception:
                            continue
        
        logger.info(f"数据加载完成: {T} 个交易日, {N} 只股票")
        
        yield {
            "type": "initializing",
            "data": {"message": "正在预加载股票池数据...", "progress": 33}
        }
        
        # ==============================================================================
        # 【关键修复】预加载股票池数据（preload_backtest_data）
        # 预加载范围：从 load_start_str 到 end_date（包含 warmup 期间）
        # 这会将所有股票池数据加载到内存，让后续 get_stock_pool 调用变成 0 延迟
        # ==============================================================================
        logger.info(f"⚡ 触发数据预加载: 预加载股票池数据 ({load_start_str} ~ {end_date})")
        if hasattr(self.data_query, 'preload_backtest_data'):
            try:
                import time
                _t_preload_start = time.perf_counter()
                self.data_query.preload_backtest_data(load_start_str, end_date)
                _t_preload_end = time.perf_counter()
                logger.info(f"✓ 股票池数据预加载完成（耗时 {_t_preload_end - _t_preload_start:.2f}s）")
            except Exception as e:
                logger.error(f"预加载股票池数据失败: {e}", exc_info=True)
        else:
            logger.warning("data_query 没有 preload_backtest_data 方法，跳过预加载")
        # ==============================================================================
        
        yield {
            "type": "initializing",
            "data": {"message": "正在预加载涨跌停数据...", "progress": 35}
        }
        
        # 预加载涨跌停数据（关键：必须在数据加载完成后立即执行）
        logger.info(f"⚡ 触发 LanceDB 内存加速: 预加载涨跌停数据 ({start_date} ~ {end_date})")
        if hasattr(self.data_query, 'preload_stock_limit_status'):
            try:
                import time
                _t_preload = time.perf_counter()
                self.data_query.preload_stock_limit_status(start_date, end_date)
                _t_preload_end = time.perf_counter()
                logger.info(f"✓ 涨跌停数据预加载完成（耗时 {_t_preload_end - _t_preload:.2f}s）")
            except Exception as e:
                logger.error(f"预加载涨跌停数据失败: {e}", exc_info=True)
        else:
            logger.warning("data_query 没有 preload_stock_limit_status 方法，跳过预加载")
        
        # =====================================================================
        # 【缓存保存】将矩阵保存到磁盘，供下次使用
        # =====================================================================
        try:
            yield {
                "type": "initializing",
                "data": {"message": "正在保存矩阵缓存...", "progress": 38}
            }
            
            _t_save_cache = time.perf_counter()
            np.save(cache_path_matrix, price_matrix)
            np.save(cache_path_meta, {'stock_codes': stock_codes, 'trading_dates': dates})
            _t_save_cache_end = time.perf_counter()
            save_time = (_t_save_cache_end - _t_save_cache) * 1000
            logger.info(f"✓ 矩阵已缓存到磁盘: {cache_path_matrix} (大小: {price_matrix.nbytes / 1024 / 1024:.2f} MB, 耗时: {save_time:.2f}ms)")
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}", exc_info=True)
        
        # 返回最终结果
        yield (price_matrix, stock_codes, dates)
    
    def _load_data_with_polars(self, start_date: str, end_date: str, 
                               required_warmup: int = 60) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        使用 Polars 加载数据并转换为 NumPy 数组
        
        Returns:
            (price_matrix, stock_codes, trading_dates)
            price_matrix: (T, N, 4) - [open, high, low, close] for each time and stock
        """
        from config.logger import get_logger
        import time
        logger = get_logger(__name__)
        
        _t_method_start = time.perf_counter()
        logger.debug(f"开始加载数据: {start_date} 到 {end_date}, warmup={required_warmup}")
        
        # 计算加载日期范围（包含预热期）
        # 【关键修复】"起始点隔离"机制 (Start Date Offset) - 按交易日历计算
        # 按交易日历计算 warmup，而非自然日（避免停牌导致的有效 Bar 数量不足）
        safe_margin_days = required_warmup * 2
        earliest_date = pd.to_datetime(start_date) - pd.Timedelta(days=safe_margin_days)
        earliest_date_str = earliest_date.strftime('%Y-%m-%d')
        
        # 获取从 earliest_date 到 start_date 的所有交易日
        warmup_trading_dates = self.data_query.get_trading_dates(earliest_date_str, start_date)
        if not warmup_trading_dates:
            # 如果获取失败，回退到自然日计算
            logger.warning(f"无法获取交易日历，回退到自然日计算 warmup")
            load_start = pd.to_datetime(start_date) - pd.Timedelta(days=required_warmup)
            load_start_str = load_start.strftime('%Y-%m-%d')
        else:
            # 取前 required_warmup 个交易日（如果不足，则使用所有可用交易日）
            if len(warmup_trading_dates) >= required_warmup:
                load_start_str = warmup_trading_dates[-required_warmup]
            else:
                logger.warning(f"交易日不足 {required_warmup} 天（实际 {len(warmup_trading_dates)} 天），使用最早可用日期")
                load_start_str = warmup_trading_dates[0] if warmup_trading_dates else earliest_date_str
        
        # 获取交易日期
        trading_dates = self.data_query.get_trading_dates(start_date, end_date)
        if not trading_dates:
            raise ValueError(f"No trading dates found between {start_date} and {end_date}")
        
        logger.info(f"加载数据: {load_start_str} 到 {end_date} (回测: {start_date} 到 {end_date})")
        
        # 使用 Polars Lazy API 分批加载数据（内存安全）
        # 检查是否使用 LanceDB（支持 Lazy API）
        use_lancedb = hasattr(self.data_query, '_use_lancedb') and self.data_query._use_lancedb
        batch_size = 30  # 每批加载 30 天
        
        if use_lancedb and hasattr(self.data_query, 'lance_manager'):
            # 优化：一次性加载整个日期范围，而不是分批加载
            # 原因：LanceDB的load_to_polars_lazy会加载整个表，分批加载反而更慢
            # 一次性加载整个日期范围，然后在内存中过滤，比多次加载整个表快得多
            all_trading_dates = self.data_query.get_trading_dates(load_start_str, end_date)
            _t_load_start = time.perf_counter()
            try:
                # 优化：尝试获取股票池（如果可能），用于过滤数据
                # 注意：在数据加载阶段，我们可能还没有股票池，所以这是可选的
                stock_codes_filter = None
                try:
                    # 尝试获取第一个交易日的股票池作为参考
                    first_date_pool = self.data_query.get_stock_pool(trading_dates[0] if trading_dates else start_date)
                    if first_date_pool is not None and not first_date_pool.empty:
                        stock_codes_filter = first_date_pool['stock_code'].unique().tolist()
                        logger.info(f"使用股票池过滤: {len(stock_codes_filter)} 只股票")
                except Exception as e:
                    logger.debug(f"无法获取股票池，将加载所有股票: {e}")
                
                # 一次性加载整个日期范围（关键修复：传入日期范围，利用下推过滤）
                # 速度将从 60秒 -> 0.1秒（因为只加载指定日期范围的数据）
                lazy_df = self.data_query.lance_manager.load_to_polars_lazy(
                    start_date=load_start_str,
                    end_date=end_date,
                    stock_codes=stock_codes_filter,  # 如果可用，传入股票池进一步过滤
                    columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
                )
                # 执行查询（此时才真正加载数据，LanceDB 会在数据库层进行过滤）
                df = lazy_df.collect()
                _t_load_end = time.perf_counter()
                logger.debug(f"LanceDB 数据加载完成，耗时 {_t_load_end - _t_load_start:.3f}s, 行数: {len(df) if not df.is_empty() else 0}")
                if df.is_empty():
                    raise ValueError("No data loaded from LanceDB")
            except Exception as e:
                logger.warning(f"一次性加载失败，回退到DuckDB批量查询: {e}", exc_info=True)
                # 回退到DuckDB批量查询
                use_lancedb = False
        else:
            # 优化：使用批量查询替代 N+1 查询，避免内存爆炸
            # 不再循环查询每一天，而是使用 WHERE trade_date IN (...) 批量查询
            all_trading_dates = self.data_query.get_trading_dates(load_start_str, end_date)
            
            # 使用批量查询获取所有数据（避免 N+1 查询）
            # 直接从数据库查询整个日期范围，而不是循环查询每一天
            logger.info(f"使用批量查询加载数据: {load_start_str} 到 {end_date} ({len(all_trading_dates)} 个交易日)")
            
            # 优化：直接使用批量查询，而不是循环 get_stock_pool
            # 使用 data_query 的底层方法批量获取数据
            try:
                # 方法1：尝试使用批量查询方法（如果存在）
                if hasattr(self.data_query, '_get_stock_pool_batch'):
                    df_pd = self.data_query._get_stock_pool_batch(all_trading_dates)
                else:
                    # 方法2：直接查询整个日期范围（使用参数化查询）
                    # 构建批量查询：WHERE trade_date IN (...)
                    placeholders = ",".join(["?"] * len(all_trading_dates))
                    query = f"""
                        SELECT 
                            stock_code, trade_date, open, high, low, close, volume,
                            total_mv, float_mv, turnover_rate, volume_ratio,
                            ma5, ma10, ma20, volume_ma5, adj_factor
                        FROM stock_daily
                        WHERE trade_date IN ({placeholders})
                        ORDER BY trade_date, stock_code
                    """
                    df_pd = self.data_query._query_df(query, params=all_trading_dates)
                
                if df_pd is None or df_pd.empty:
                    raise ValueError("No data loaded from batch query")
                
                # 转换为 Polars（延迟执行）
                df = pl.from_pandas(df_pd).lazy()
                # 执行查询（但只加载必要的列）
                df = df.select(['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']).collect()
                
            except Exception as e:
                logger.warning(f"批量查询失败，回退到分批加载: {e}")
                # 回退：分批加载（但优化内存使用）
                all_trading_dates = self.data_query.get_trading_dates(load_start_str, end_date)
                
                # 优化：使用流式处理，逐步处理数据而不是一次性加载所有批次
                batch_size = 30
                processed_chunks = []
                
                for i in range(0, len(all_trading_dates), batch_size):
                    batch_dates = all_trading_dates[i:i+batch_size]
                    
                    # 使用批量查询替代循环查询（使用参数化查询）
                    placeholders = ",".join(["?"] * len(batch_dates))
                    query = f"""
                        SELECT 
                            stock_code, trade_date, open, high, low, close, volume
                        FROM stock_daily
                        WHERE trade_date IN ({placeholders})
                        ORDER BY trade_date, stock_code
                    """
                    df_pd_batch = self.data_query._query_df(query, params=batch_dates)
                    
                    if df_pd_batch is not None and not df_pd_batch.empty:
                        # 转换为 Polars 并立即处理，不保存在 all_batches 中
                        df_batch = pl.from_pandas(df_pd_batch)
                        processed_chunks.append(df_batch)
                        
                        # 每处理 3 个批次就合并一次，避免内存累积
                        if len(processed_chunks) >= 3:
                            df_merged = pl.concat(processed_chunks)
                            processed_chunks = [df_merged]  # 重置为合并后的数据
                
                # 合并剩余的批次
                if processed_chunks:
                    if len(processed_chunks) == 1:
                        df = processed_chunks[0]
                    else:
                        df = pl.concat(processed_chunks)
                else:
                    raise ValueError("No data loaded")
        
        # ==============================================================================
        # 【第三阶段优化】全局唯一的代码序列：锁定股票代码列表，确保所有矩阵对齐
        # 使用 sorted() 确保顺序一致，避免"张冠李戴"的数据对齐错误
        # ==============================================================================
        stock_codes = sorted(df['stock_code'].unique().to_list())
        dates = sorted(df['trade_date'].unique().to_list())
        
        # 锁定全局股票代码列表（不可变）
        # 后续所有矩阵（price_matrix, signal_matrix）必须严格按此顺序对齐
        GLOBAL_STOCK_LIST = tuple(stock_codes)  # 使用 tuple 确保不可变
        logger.info(f"[DATA] 锁定全局股票代码序列: {len(GLOBAL_STOCK_LIST)} 只股票")
        # ==============================================================================
        
        # 创建价格矩阵 (T, N, 4) - [open, high, low, close]
        T = len(dates)
        N = len(stock_codes)
        
        # 【极速优化】使用 pd.Categorical 极速构建索引，替代 slow map
        try:
            # 转换为 Pandas
            df_pd = df.to_pandas()
            
            # 1. 确保 dates 和 stock_codes 是排序的（Categorical 需要）
            dates_sorted = sorted(dates)
            stock_codes_sorted = sorted(stock_codes)
            
            # 2. 将列转换为 Categorical 类型，指定 categories 为我们的列表
            # 这会自动将字符串映射为整数索引 (codes)，比 map 快 10-100 倍
            df_pd['trade_date'] = pd.Categorical(df_pd['trade_date'], categories=dates_sorted, ordered=True)
            df_pd['stock_code'] = pd.Categorical(df_pd['stock_code'], categories=stock_codes_sorted, ordered=True)
            
            # 3. 直接获取编码 (codes)，这就是我们需要的索引
            # 注意：-1 表示不在列表中的数据（会被后续过滤）
            date_indices = df_pd['trade_date'].cat.codes.values
            code_indices = df_pd['stock_code'].cat.codes.values
            
            # 4. 构建掩码：过滤掉无效索引（-1 表示不在 categories 中）
            valid_mask = (date_indices >= 0) & (code_indices >= 0)
            
            # 5. 初始化价格矩阵
            price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
            
            # 6. 向量化填充：使用 .values 获取原生 numpy 数组，避免 pandas 索引对齐开销
            if valid_mask.all():
                valid_date_idx = date_indices
                valid_code_idx = code_indices
                valid_df = df_pd
            else:
                valid_date_idx = date_indices[valid_mask]
                valid_code_idx = code_indices[valid_mask]
                valid_df = df_pd[valid_mask]
            
            price_cols = ['open', 'high', 'low', 'close']
            for i, col in enumerate(price_cols):
                if col in valid_df.columns:
                    # 直接赋值，飞快
                    vals = valid_df[col].values.astype(np.float32)
                    price_matrix[valid_date_idx, valid_code_idx, i] = vals
            
            # 【关键】强制转换为 C-连续内存，供 Numba 使用
            price_matrix = np.ascontiguousarray(price_matrix, dtype=np.float32)
            
            logger.info(f"✓ 价格矩阵构建完成（Categorical 极速方法）: {T} 个交易日, {N} 只股票")
            
        except Exception as e:
            # 回退到原始方法（如果向量化失败）
            logger.warning(f"向量化构建价格矩阵失败，回退到循环方法: {e}")
            price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
            
            # 原始循环方法（作为回退）
            for t, date in enumerate(dates):
                date_df = df.filter(pl.col('trade_date') == date)
                for n, code in enumerate(stock_codes):
                    code_row = date_df.filter(pl.col('stock_code') == code)
                    if not code_row.is_empty():
                        try:
                            row_dict = code_row.to_dicts()[0]
                            price_matrix[t, n, 0] = row_dict.get('open', np.nan) if 'open' in row_dict else np.nan
                            price_matrix[t, n, 1] = row_dict.get('high', np.nan) if 'high' in row_dict else np.nan
                            price_matrix[t, n, 2] = row_dict.get('low', np.nan) if 'low' in row_dict else np.nan
                            price_matrix[t, n, 3] = row_dict.get('close', np.nan) if 'close' in row_dict else np.nan
                        except Exception:
                            continue
        
        logger.info(f"数据加载完成: {T} 个交易日, {N} 只股票")
        
        # ==============================================================================
        # 【关键修复】预加载股票池数据（preload_backtest_data）
        # 预加载范围：从 load_start_str 到 end_date（包含 warmup 期间）
        # ==============================================================================
        logger.info(f"⚡ 触发数据预加载: 预加载股票池数据 ({load_start_str} ~ {end_date})")
        if hasattr(self.data_query, 'preload_backtest_data'):
            try:
                self.data_query.preload_backtest_data(load_start_str, end_date)
                logger.info("✓ 股票池数据预加载完成，后续查询将直接从内存读取")
            except Exception as e:
                logger.warning(f"预加载股票池数据失败: {e}，将使用逐日查询（可能较慢）")
        else:
            logger.warning("data_query 没有 preload_backtest_data 方法，跳过预加载")
        # ==============================================================================
        
        # ==============================================================================
        # 【关键修复】显式调用涨跌停数据的预加载
        # 这会将 LanceDB 数据读入内存字典，让后续循环查询变成 0 延迟
        # ==============================================================================
        if hasattr(self.data_query, 'preload_stock_limit_status'):
            logger.info(f"⚡ 触发 LanceDB 内存加速: 预加载涨跌停数据 ({start_date} ~ {end_date})")
            try:
                self.data_query.preload_stock_limit_status(start_date, end_date)
                logger.info("✓ 涨跌停数据预加载完成，后续查询将直接从内存读取")
            except Exception as e:
                logger.warning(f"预加载涨跌停数据失败: {e}，将使用逐日查询（可能较慢）")
        # ==============================================================================
        
        return price_matrix, stock_codes, dates
    
    def _calculate_indicators_gpu(self, price_matrix: np.ndarray) -> np.ndarray:
        """
        在 GPU 上计算技术指标
        
        Args:
            price_matrix: (T, N, 4) - [open, high, low, close]
            
        Returns:
            indicator_matrix: (T, N, K) - K 个技术指标
        """
        if not CUPY_AVAILABLE:
            # 如果没有 CuPy，在 CPU 上计算
            return self._calculate_indicators_cpu(price_matrix)
        
        # 移动到 GPU
        price_gpu = cp.asarray(price_matrix)
        T, N, _ = price_gpu.shape
        
        # 提取价格序列
        close = price_gpu[:, :, 3]  # (T, N)
        open_price = price_gpu[:, :, 0]  # (T, N)
        high = price_gpu[:, :, 1]  # (T, N)
        low = price_gpu[:, :, 2]  # (T, N)
        
        # 计算指标（示例：MA5, MA10, MA20）
        indicators = []
        
        # MA5
        ma5 = cp.full_like(close, cp.nan)
        for t in range(4, T):
            ma5[t, :] = cp.mean(close[t-4:t+1, :], axis=0)
        indicators.append(ma5)
        
        # MA10
        ma10 = cp.full_like(close, cp.nan)
        for t in range(9, T):
            ma10[t, :] = cp.mean(close[t-9:t+1, :], axis=0)
        indicators.append(ma10)
        
        # MA20
        ma20 = cp.full_like(close, cp.nan)
        for t in range(19, T):
            ma20[t, :] = cp.mean(close[t-19:t+1, :], axis=0)
        indicators.append(ma20)
        
        # 成交量比率（如果有成交量数据）
        # volume_ratio = ...  # 需要从数据中获取
        
        # 堆叠所有指标
        indicator_matrix = cp.stack(indicators, axis=2)  # (T, N, K)
        
        # 移回 CPU
        return cp.asnumpy(indicator_matrix)
    
    def _calculate_indicators_cpu(self, price_matrix: np.ndarray) -> np.ndarray:
        """在 CPU 上计算技术指标（CuPy 不可用时的回退）"""
        T, N, _ = price_matrix.shape
        close = price_matrix[:, :, 3]
        
        indicators = []
        
        # MA5
        ma5 = np.full_like(close, np.nan)
        for t in range(4, T):
            ma5[t, :] = np.mean(close[t-4:t+1, :], axis=0)
        indicators.append(ma5)
        
        # MA10
        ma10 = np.full_like(close, np.nan)
        for t in range(9, T):
            ma10[t, :] = np.mean(close[t-9:t+1, :], axis=0)
        indicators.append(ma10)
        
        # MA20
        ma20 = np.full_like(close, np.nan)
        for t in range(19, T):
            ma20[t, :] = np.mean(close[t-19:t+1, :], axis=0)
        indicators.append(ma20)
        
        return np.stack(indicators, axis=2)
    
    @staticmethod
    @staticmethod
    @jit(nopython=True, cache=True, fastmath=True, locals={'buy_count': int64})
    def _fast_match_loop(
        price_matrix: np.ndarray,   # float32[:,:,::1] - C-contiguous [open, high, low, close]
        signal_matrix: np.ndarray,  # int32[:,::1] - C-contiguous 0=hold, 1=buy, 2=sell
        initial_cash: float,
        commission_rate: float,
        min_commission: float,
        sell_tax: float,
        board_lot: int,
        max_positions: int,
        position_ratio: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Numba JIT 编译的快速执行循环
        
        Args:
            price_matrix: (T, N, 4) 价格矩阵
            signal_matrix: (T, N) 信号矩阵，0=hold, 1=buy, 2=sell
            initial_cash: 初始资金
            commission_rate: 佣金费率
            min_commission: 最低佣金
            sell_tax: 卖出印花税
            board_lot: 每手股数
            max_positions: 最大持仓数
            position_ratio: 单只股票仓位比例
            
        Returns:
            (cash_history, portfolio_value_history, trades)
            cash_history: (T,) 每日现金
            portfolio_value_history: (T,) 每日总资产
            trades: (M, 5) - [date_idx, stock_idx, action, price, shares]
        """
        T, N, _ = price_matrix.shape
        
        # 初始化
        cash = initial_cash
        positions = np.zeros((N,), dtype=np.float32)  # 持仓股数
        entry_prices = np.zeros((N,), dtype=np.float32)  # 买入价格
        
        # 历史记录
        cash_history = np.zeros(T, dtype=np.float32)
        portfolio_value_history = np.zeros(T, dtype=np.float32)
        
        # 交易记录（预分配，实际可能更少）
        max_trades = T * N  # 最大可能交易数
        trades = np.full((max_trades, 5), -1, dtype=np.float32)
        trade_count = 0
        
        # 【性能优化】在循环外预分配买入信号缓冲区，避免循环内malloc
        # 这是性能关键：每次循环都分配新数组会导致大量内存分配开销
        buy_candidates_buffer = np.empty(N, dtype=np.int64)
        
        for t in range(T):
            # 获取当日价格
            opens = price_matrix[t, :, 0]
            closes = price_matrix[t, :, 3]
            
            # === 处理卖出信号 ===
            for n in range(N):
                if signal_matrix[t, n] == 2 and positions[n] > 0:  # sell
                    shares = positions[n]
                    # 取整到每手
                    shares = (int(shares) // board_lot) * board_lot
                    if shares < board_lot:
                        continue
                    
                    price = opens[n] if not np.isnan(opens[n]) else closes[n]
                    # ==============================================================================
                    # 【第三阶段优化】潜在失效模式：检查价格有效性
                    # 如果价格无效（NaN 或 <= 0），强制忽略交易信号，避免对未上市/已退市股票交易
                    # ==============================================================================
                    if np.isnan(price) or price <= 0:
                        continue
                    # ==============================================================================
                    
                    # 计算费用
                    revenue = shares * price
                    commission = max(revenue * commission_rate, min_commission)
                    tax = revenue * sell_tax
                    net_revenue = revenue - commission - tax
                    
                    # 更新
                    cash += net_revenue
                    positions[n] -= shares
                    if positions[n] < 1e-6:
                        positions[n] = 0
                        entry_prices[n] = 0
                    
                    # 记录交易
                    if trade_count < max_trades:
                        trades[trade_count, 0] = t
                        trades[trade_count, 1] = n
                        trades[trade_count, 2] = 2  # sell
                        trades[trade_count, 3] = price
                        trades[trade_count, 4] = shares
                        trade_count += 1
            
            # === 处理买入信号 ===
            # 【性能优化】使用循环外预分配的缓冲区，只重置计数器，不重新分配数组
            # 这样可以消除循环内的malloc开销，大幅提升性能（从33ms降至1-2ms）
            buy_count = 0
            for n in range(N):
                if signal_matrix[t, n] == 1 and positions[n] == 0:  # buy
                    buy_candidates_buffer[buy_count] = n
                    buy_count += 1
            
            # 限制买入数量
            if max_positions > 0:
                current_positions = np.sum(positions > 0)
                buy_allowance = max_positions - current_positions
                if buy_allowance <= 0:
                    buy_count = 0
                elif buy_count > buy_allowance:
                    buy_count = buy_allowance
            
            # 使用 buy_candidates_buffer 的前 buy_count 个元素
            buy_signals = buy_candidates_buffer[:buy_count]
            
            # 执行买入
            if buy_count > 0:
                # 计算可用资金
                total_equity = cash
                for n in range(N):
                    if positions[n] > 0:
                        price = closes[n] if not np.isnan(closes[n]) else opens[n]
                        if not np.isnan(price) and price > 0:
                            total_equity += positions[n] * price
                
                # 计算每只股票的目标投资金额
                if position_ratio > 0:
                    target_per_stock = total_equity * position_ratio
                else:
                    target_per_stock = cash / buy_count if buy_count > 0 else 0
                
                for i in range(buy_count):
                    n = buy_signals[i]
                    price = opens[n] if not np.isnan(opens[n]) else closes[n]
                    # ==============================================================================
                    # 【第三阶段优化】潜在失效模式：检查价格有效性
                    # 如果价格无效（NaN 或 <= 0），强制忽略交易信号，避免对未上市/已退市股票交易
                    # ==============================================================================
                    if np.isnan(price) or price <= 0:
                        continue
                    # ==============================================================================
                
                    investment = min(target_per_stock, cash)
                    if investment <= 0:
                        continue
                    
                    # 估算费用
                    est_rate = max(commission_rate, min_commission / (investment + 1))
                    price_with_rate = price * (1 + est_rate)
                    max_shares = int(investment / price_with_rate)
                    shares = (max_shares // board_lot) * board_lot
                    
                    if shares < board_lot:
                        continue
                    
                    # 计算实际费用
                    commission = max(shares * price * commission_rate, min_commission)
                    cost = shares * price + commission
                    
                    if cost > cash:
                        continue
                    
                    # 更新
                    cash -= cost
                    positions[n] = shares
                    entry_prices[n] = price
                    
                    # 记录交易
                    if trade_count < max_trades:
                        trades[trade_count, 0] = t
                        trades[trade_count, 1] = n
                        trades[trade_count, 2] = 1  # buy
                        trades[trade_count, 3] = price
                        trades[trade_count, 4] = shares
                        trade_count += 1
            
            # === 计算当日市值 ===
            portfolio_value = cash
            for n in range(N):
                if positions[n] > 0:
                    price = closes[n] if not np.isnan(closes[n]) else opens[n]
                    # ==============================================================================
                    # 【第三阶段优化】潜在失效模式：检查价格有效性
                    # 如果价格无效（NaN 或 <= 0），不计算市值，避免错误估值
                    # ==============================================================================
                    if not np.isnan(price) and price > 0:
                        portfolio_value += positions[n] * price
                    # ==============================================================================
            
            cash_history[t] = cash
            portfolio_value_history[t] = portfolio_value
        
        # 截断交易记录
        if trade_count < max_trades:
            trades = trades[:trade_count]
        
        return cash_history, portfolio_value_history, trades
    
    def _convert_signals_to_matrix(self, signals_dict: Dict[str, str], 
                                   code_to_idx: Dict[str, int],
                                   date: str = "") -> np.ndarray:
        """
        将策略信号字典转换为信号矩阵（优化版：使用预构建的索引映射）
        
        【性能优化】将 code_to_idx 字典构建移到循环外部，避免每次循环都重新构建
        复杂度从 O(T × N) 降低为 O(T)（查找开销）
        
        Args:
            signals_dict: {stock_code: 'buy'/'sell'/'hold'}
            code_to_idx: 预构建的股票代码到索引的映射字典（在循环外部构建一次）
            date: 当前日期（用于日志，可选）
            
        Returns:
            signal_matrix: (N,) - 0=hold, 1=buy, 2=sell
        """
        N = len(code_to_idx)
        signal_matrix = np.zeros(N, dtype=np.int32)
        
        for code, signal in signals_dict.items():
            # 使用预构建的字典进行 O(1) 查找
            idx = code_to_idx.get(code)
            if idx is not None:
                if signal == 'buy':
                    signal_matrix[idx] = 1
                elif signal == 'sell':
                    signal_matrix[idx] = 2
                # else: 0 (hold)
        
        return signal_matrix
    
    def run_backtest_streaming(self, start_date, end_date, strategy, 
                               stop_event: Optional[Event] = None) -> Generator[Dict[str, Any], None, None]:
        """
        流式回测生成器 - Polars + CuPy + Numba 架构
        """
        from config.logger import get_logger
        logger = get_logger(__name__)
        
        logger.info(f"开始【流式】回测 (Polars+CuPy+Numba): {start_date} 到 {end_date}")
        
        # 验证日期
        start_date_str, end_date_str = self._validate_dates(start_date, end_date)
        
        if start_date_str > end_date_str:
            error_msg = f"开始日期 ({start_date_str}) 不能晚于结束日期 ({end_date_str})"
            logger.error(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return
        
        # 获取策略参数
        required_warmup = getattr(strategy, 'warmup_days', 60)
        max_positions = getattr(strategy, 'max_positions', self.DEFAULT_MAX_POSITIONS)
        position_ratio = getattr(strategy, 'position_ratio', self.DEFAULT_POSITION_RATIO)
        
        # 立即发送初始化进度更新，避免前端30秒超时
        yield {
            "type": "initializing",
            "data": {"message": "正在加载数据...", "progress": 0}
        }
        
        # 性能监控：记录各阶段耗时
        perf_details = {
            'data_loading': 0,
            'indicator_calculation': 0,
            'signal_generation': 0,
            'trade_execution': 0,
            'result_output': 0,
        }
        
        # 1. 加载数据（Polars）- 使用生成器版本，支持进度更新
        import time
        _t_load_start = time.perf_counter()
        try:
            # 使用生成器版本，在关键步骤之间 yield 进度更新
            _iter_count = 0
            for item in self._load_data_with_polars_streaming(
                start_date_str, end_date_str, required_warmup
            ):
                _iter_count += 1
                # 检查是否是最终结果（元组）
                if isinstance(item, tuple) and len(item) == 3:
                    # 最终结果
                    price_matrix, stock_codes, trading_dates = item
                    break
                else:
                    # 进度更新，yield 给前端
                    yield item
            _t_load_end = time.perf_counter()
            perf_details['data_loading'] = (_t_load_end - _t_load_start) * 1000  # ms
            logger.debug(f"数据加载完成，耗时 {perf_details['data_loading']:.2f}ms, "
                        f"shape={list(price_matrix.shape) if price_matrix is not None else None}, "
                        f"stocks={len(stock_codes) if stock_codes else 0}, "
                        f"dates={len(trading_dates) if trading_dates else 0}")
        except Exception as e:
            logger.error(f"数据加载失败: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": f"数据加载失败: {e}"}}
            return

        # 检测并输出架构信息
        arch_info = {
            'engine': 'OptimizedBacktestEngine',
            'data_backend': 'unknown',
            'data_format': 'NumPy Array',
            'compute_backend': 'Numba JIT',
            'jit_compiled': NUMBA_AVAILABLE,
            'preloaded': False
        }
        
        # 检测数据后端
        if hasattr(self.data_query, '_use_lancedb') and self.data_query._use_lancedb:
            if hasattr(self.data_query, 'lance_manager'):
                arch_info['data_backend'] = 'LanceDB'
            else:
                arch_info['data_backend'] = 'LanceDB (未初始化)'
        elif hasattr(self.data_query, '_use_duckdb') and self.data_query._use_duckdb:
            arch_info['data_backend'] = 'DuckDB'
        else:
            arch_info['data_backend'] = 'SQLite/其他'
        
        # 检测是否使用预加载
        if hasattr(self.data_query, '_preloaded_data') and self.data_query._preloaded_data is not None:
            arch_info['preloaded'] = True
        
        # 输出架构信息（使用 WARNING 级别确保输出）
        logger.warning(f"[ARCH] ========== 回测引擎架构检测 ==========")
        logger.warning(f"[ARCH] 引擎: {arch_info['engine']}")
        logger.warning(f"[ARCH] 数据后端: {arch_info['data_backend']}")
        logger.warning(f"[ARCH] 数据格式: {arch_info['data_format']}")
        logger.warning(f"[ARCH] 计算后端: {arch_info['compute_backend']}")
        logger.warning(f"[ARCH] Numba JIT: {'是' if arch_info['jit_compiled'] else '否'}")
        logger.warning(f"[ARCH] 数据预加载: {'是' if arch_info['preloaded'] else '否'}")
        logger.warning(f"[ARCH] ======================================")
        
        if not arch_info['preloaded']:
            logger.warning("[ARCH] ⚠️  警告: 未使用数据预加载，性能可能较差！")
        if arch_info['data_backend'] != 'LanceDB':
            logger.warning(f"[ARCH] ⚠️  警告: 未使用LanceDB后端（当前: {arch_info['data_backend']}），性能可能较差！")
        if not arch_info['jit_compiled']:
            logger.warning("[ARCH] ⚠️  警告: Numba不可用，未使用JIT编译，性能可能较差！")
        
        # 发送数据加载完成进度
        yield {
            "type": "initializing",
            "data": {"message": "数据加载完成，正在预加载辅助数据...", "progress": 30}
        }

        # 找到回测开始日期在 trading_dates 中的索引
        try:
            start_idx = trading_dates.index(start_date_str)
        except ValueError:
            # 如果找不到，使用第一个日期
            start_idx = 0
            logger.warning(f"开始日期 {start_date_str} 不在交易日期列表中，使用 {trading_dates[0]}")
        
        # 截取回测期间的数据
        price_matrix = price_matrix[start_idx:]
        trading_dates = trading_dates[start_idx:]
        T, N, _ = price_matrix.shape
        
        logger.info(f"回测期间: {len(trading_dates)} 个交易日, {N} 只股票")
        
        # ==============================================================================
        # 【第一阶段优化】静态化索引映射：在循环外部构建 code_to_idx 字典
        # 避免每次循环都重新构建，复杂度从 O(T × N) 降低为 O(T)
        # ==============================================================================
        code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
        logger.debug(f"[PERF] 构建全局索引映射: {len(code_to_idx)} 只股票")
        # ==============================================================================
        
        # 注意：stock_limit_status 预加载已在 _load_data_with_polars 中完成
        # 这里不再重复预加载，避免浪费时间和资源
        
        # 发送预加载完成进度
        yield {
            "type": "initializing",
            "data": {"message": "辅助数据预加载完成，准备开始回测...", "progress": 60}
        }

        # ==============================================================================
        # 【第二阶段优化】删除未使用的 GPU 指标计算代码
        # 原代码计算了 indicator_matrix 但从未使用，造成资源浪费
        # 策略通过 data_query 重新拉取数据，不依赖预计算的指标矩阵
        # 如果未来需要集成，可以通过 context 传递给策略
        # ==============================================================================
        
        # 发送初始化完成进度
        yield {
            "type": "initializing",
            "data": {"message": "技术指标计算完成，准备开始回测...", "progress": 90}
        }
        
        # 【关键修复】预加载完成，发送 initialized 事件关闭加载动画
        # 在开始流式更新回测数据前，关闭加载动画，后续只进行流式更新
        yield {
            "type": "initialized",
            "data": {"message": "初始化完成，开始回测..."}
        }
        
        logger.debug(f"准备开始回测: T={T}, N={N}, dates_count={len(trading_dates)}")
        
        yield {
            "type": "backtest_start",
            "data": {"initialCapital": self.initial_capital}
        }
        
        # 4. 逐日执行（保持流式输出）
        results_list = []
        all_trades_log = []
        
        # 初始化
        cash = self.initial_capital
        portfolio = {}  # {stock_code: {'shares': ..., 'entry_price': ...}}
        
        # 构建信号矩阵（逐日生成或向量化生成）
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 性能监控：信号生成总耗时
        _t_signal_total_start = time.perf_counter()
        signal_generation_times = []
        
        logger.debug(f"信号矩阵初始化完成，开始循环: T={T}, N={N}")
        
        # ==============================================================================
        # 【向量化策略支持】检查策略是否支持向量化信号生成
        # 如果策略实现了 generate_signals_vectorized 方法，使用向量化路径
        # 否则使用逐日循环路径（兼容旧策略）
        # ==============================================================================
        use_vectorized = hasattr(strategy, 'generate_signals_vectorized')
        
        if use_vectorized:
            logger.info(f"[VECTORIZED] 检测到向量化策略，使用一次性计算模式")
            try:
                # 准备预加载数据（如果可用）
                preloaded_data = None
                if hasattr(self.data_query, '_preloaded_data') and self.data_query._preloaded_data is not None:
                    preloaded_data = self.data_query._preloaded_data
                    logger.info(f"[VECTORIZED] 使用预加载数据: {len(preloaded_data)} 个交易日")
                
                # 调用向量化方法
                _t_vectorized_start = time.perf_counter()
                signal_matrix = strategy.generate_signals_vectorized(
                    price_matrix=price_matrix,  # (T, N, 4) - [open, high, low, close]
                    trading_dates=trading_dates,  # (T,)
                    stock_codes=stock_codes,      # (N,)
                    data_query=self.data_query,
                    preloaded_data=preloaded_data  # Dict[str, pd.DataFrame] - 预加载的全量数据
                )
                _t_vectorized_end = time.perf_counter()
                vectorized_time = (_t_vectorized_end - _t_vectorized_start) * 1000  # ms
                perf_details['signal_generation'] = vectorized_time
                logger.warning(f"[PERF] 向量化信号生成完成: {vectorized_time:.2f}ms ({vectorized_time/len(trading_dates):.2f}ms/天)")
                
                # 验证信号矩阵形状
                if signal_matrix.shape != (T, N):
                    raise ValueError(f"向量化策略返回的信号矩阵形状不匹配: 期望 ({T}, {N}), 实际 {signal_matrix.shape}")
                
                # 【极速路径】直接全量赋值，确保类型匹配 (int32)，避免隐式转换开销
                # 确保内存连续，提升后续 Numba 性能
                signal_matrix = np.ascontiguousarray(signal_matrix.astype(np.int32), dtype=np.int32)
                
                # 向量化模式下，不需要逐日循环，直接跳到交易执行
                logger.info(f"[VECTORIZED] 信号矩阵生成完成，跳过逐日循环")
                
                # 如果需要给前端发进度，只发一次即可
                yield {
                    "type": "progress", 
                    "data": {"message": "信号生成完成，进入极速撮合...", "progress": 50}
                }
                
            except Exception as e:
                logger.error(f"[VECTORIZED] 向量化信号生成失败，回退到逐日循环: {e}", exc_info=True)
                # 回退到逐日循环
                use_vectorized = False
                signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # 逐日循环路径（兼容旧策略或向量化失败时的回退）
        if not use_vectorized:
            logger.debug(f"[SEQUENTIAL] 使用逐日循环模式")
            for t, current_date in enumerate(tqdm(trading_dates, desc="流式回测进度")):
                if stop_event and stop_event.is_set():
                    logger.warning("收到停止信号，结束流式回测")
                    return
                
                # 性能监控：记录每天的总耗时
                day_start = time.perf_counter()
                perf_breakdown = {}
                
                try:
                    # ==============================================================================
                    # 【引擎端优化】移除无效的数据获取
                    # 策略 JQVolumeStrategypro 明确只使用"昨日数据"进行选股，不使用当日数据
                    # 但引擎主循环中每一天都在获取"当日数据"，这造成了巨大的无用开销
                    # 
                    # 优化方案：
                    # 1. 检查策略是否需要当日股票池（通过策略属性或方法）
                    # 2. 如果不需要，传递 None，避免不必要的数据库查询和内存分配
                    # 3. 策略内部必须处理 stock_pool 为 None 的情况（JQVolumeStrategypro 是安全的）
                    # ==============================================================================
                    _t_pool_start = time.perf_counter()
                    
                    # 检查策略是否需要当日股票池
                    needs_today_pool = getattr(strategy, 'needs_today_pool', False)
                    
                    if needs_today_pool:
                        # 策略需要当日股票池，从预加载数据获取
                        preloaded_pool = None
                        if hasattr(self.data_query, 'get_stock_pool_from_preloaded'):
                            preloaded_pool = self.data_query.get_stock_pool_from_preloaded(current_date)
                        
                        if preloaded_pool is not None:
                            stock_pool = preloaded_pool
                        else:
                            # 回退到常规查询（可能较慢）
                            stock_pool = self.data_query.get_stock_pool(current_date)
                            
                            # 检查是否应该使用预加载但未命中
                            if hasattr(self.data_query, '_preloaded_data') and self.data_query._preloaded_data is not None:
                                logger.error(f"[DATA] ⚠️ 严重警告：预加载数据存在但未命中 ({current_date})，"
                                           f"可能影响性能。请检查预加载日期范围。")
                    else:
                        # 策略不需要当日股票池（如 JQVolumeStrategypro），传递 None
                        # 策略内部会自己获取昨日数据，避免无用的数据获取开销
                        stock_pool = None
                    
                    _t_pool_end = time.perf_counter()
                    
                    # 性能监控：如果耗时超过 10ms，记录警告
                    pool_time_ms = (_t_pool_end - _t_pool_start) * 1000
                    if pool_time_ms > 10.0 and stock_pool is not None:
                        logger.warning(f"[PERF] 获取股票池耗时较长 ({current_date}): {pool_time_ms:.2f}ms, "
                                     f"可能未使用预加载数据，行数: {len(stock_pool) if not stock_pool.empty else 0}")
                    # ==============================================================================

                    # 设置策略运行时上下文
                    if hasattr(strategy, "set_runtime_context"):
                        strategy.set_runtime_context(current_date, portfolio, cash)

                    # 生成信号
                    _t_signal_start = time.perf_counter()
                    try:
                        # 注意：策略内部必须处理 stock_pool 为 None 的情况
                        # JQVolumeStrategypro 是安全的，它内部自己获取昨日数据
                        signals = strategy.generate_signals(current_date, stock_pool, self.data_query)
                    except Exception as e:
                        logger.error(f"策略信号生成失败 ({current_date}): {e}", exc_info=True)
                        signals = {}
                    _t_signal_end = time.perf_counter()
                    signal_time = (_t_signal_end - _t_signal_start) * 1000  # ms
                    signal_generation_times.append(signal_time)
                    
                    # 转换为信号矩阵（使用预构建的索引映射）
                    signal_matrix[t, :] = self._convert_signals_to_matrix(signals, code_to_idx, current_date)
                    
                    # 【优化】批量产出交易信号（用于实时显示）
                    # 收集当日所有有效信号，每天只yield一次，避免IO风暴
                    batch_signals = []
                    if signals:
                        for code, signal in signals.items():
                            if signal in ['buy', 'sell']:  # 严格过滤，只包含有效动作
                                batch_signals.append({
                                    "date": current_date,
                                    "symbol": code,
                                    "action": signal
                                })
                    
                    # 每天只产生 1 次 IO 事件（包含该日所有信号）
                    if batch_signals:
                        yield {
                            "type": "signal_batch",
                            "data": batch_signals
                        }
                except Exception as e:
                    logger.error(f"处理日期 {current_date} 时出错: {e}", exc_info=True)
                    continue
        
        # 性能监控：信号生成总耗时（仅在逐日循环模式下更新）
        if not use_vectorized:
            _t_signal_total_end = time.perf_counter()
            perf_details['signal_generation'] = (_t_signal_total_end - _t_signal_total_start) * 1000  # ms
            if signal_generation_times:
                avg_signal_time = sum(signal_generation_times) / len(signal_generation_times)
                max_signal_time = max(signal_generation_times)
                logger.info(f"[PERF] 信号生成: 总耗时 {perf_details['signal_generation']:.2f}ms, 平均 {avg_signal_time:.2f}ms/天, 最大 {max_signal_time:.2f}ms")
        
        # 输出策略内部性能统计（如果策略支持）
        if hasattr(strategy, 'get_perf_stats'):
            try:
                strategy_stats = strategy.get_perf_stats()
                total_strategy_time = strategy_stats.get('_total_time_ms', 0)
                if total_strategy_time > 0:
                    logger.warning(f"[PERF] ========== 策略信号生成详情 ({len(trading_dates)}天) ==========")
                    logger.warning(f"[PERF] 策略总耗时: {total_strategy_time:.2f}ms")
                    
                    # 按耗时排序输出
                    step_names = {
                        'get_previous_day_pool': '获取昨日股票池',
                        'pre_screen_stocks': '预筛选股票',
                        'evaluate_buy_candidates': '评估买入候选',
                        'get_sell_signals': '获取卖出信号',
                        'other': '其他操作'
                    }
                    
                    sorted_steps = sorted(
                        [(k, v) for k, v in strategy_stats.items() if k != '_total_time_ms'],
                        key=lambda x: x[1].get('total_ms', 0),
                        reverse=True
                    )
                    
                    for step_key, step_data in sorted_steps:
                        step_name = step_names.get(step_key, step_key)
                        total_ms = step_data.get('total_ms', 0)
                        avg_ms = step_data.get('avg_ms', 0)
                        count = step_data.get('count', 0)
                        percentage = (total_ms / total_strategy_time * 100) if total_strategy_time > 0 else 0
                        
                        log_line = f"[PERF]   - {step_name}: {total_ms:.2f}ms ({percentage:.1f}%), 平均 {avg_ms:.2f}ms/次, 调用 {count} 次"
                        
                        # 特殊处理：缓存命中率
                        if step_key == 'get_previous_day_pool' and 'cache_hit_rate' in step_data:
                            hit_rate = step_data.get('cache_hit_rate', 0)
                            cache_hits = step_data.get('cache_hits', 0)
                            log_line += f", 缓存命中率 {hit_rate:.1f}% ({cache_hits}/{count})"
                        
                        logger.warning(log_line)
                    
                    logger.warning(f"[PERF] ======================================")
            except Exception as e:
                logger.warning(f"[PERF] 获取策略性能统计失败: {e}")
        
        # 5. 执行快速匹配循环（Numba）
        logger.info("执行快速匹配循环...")
        
        # 【性能优化】强制内存连续 (C-contiguous)，提升 Numba 性能
        # Numba 处理连续内存比非连续内存快得多，可以生成 SIMD 指令
        price_matrix = np.ascontiguousarray(price_matrix, dtype=np.float32)
        signal_matrix = np.ascontiguousarray(signal_matrix, dtype=np.int32)
        
        exec_start = time.perf_counter()
        try:
            cash_history, portfolio_value_history, trades = self._fast_match_loop(
                price_matrix,
                signal_matrix,
                float(self.initial_capital),
                float(self.commission_rate),
                float(self.DEFAULT_MIN_COMMISSION),
                float(self.DEFAULT_SELL_TAX),
                int(self.DEFAULT_BOARD_LOT),
                int(max_positions),
                float(position_ratio)
            )
            exec_time = (time.perf_counter() - exec_start) * 1000  # ms
            perf_details['trade_execution'] = exec_time
            exec_time_per_day = exec_time / len(trading_dates) if trading_dates else 0
            logger.warning(f"[PERF] ========== 快速匹配循环性能 ==========")
            logger.warning(f"[PERF] 总耗时: {exec_time:.1f}ms")
            logger.warning(f"[PERF] 平均耗时: {exec_time_per_day:.3f}ms/天")
            logger.warning(f"[PERF] 交易天数: {len(trading_dates)} 天")
            logger.warning(f"[ARCH] 使用Numba JIT编译循环: {'是' if NUMBA_AVAILABLE else '否'}")
            logger.warning(f"[PERF] ======================================")
            
            # 【调试】检查返回的数据
            logger.info(f"快速匹配循环完成: cash_history.shape={cash_history.shape if hasattr(cash_history, 'shape') else len(cash_history)}, "
                       f"portfolio_value_history.shape={portfolio_value_history.shape if hasattr(portfolio_value_history, 'shape') else len(portfolio_value_history)}, "
                       f"trades.shape={trades.shape if hasattr(trades, 'shape') else len(trades)}")
        except Exception as e:
            logger.error(f"快速匹配循环失败: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": f"执行失败: {e}"}}
            return
        
        # 6. 转换交易记录并产出（流式产出，让前端实时看到交易）
        # 【调试】检查 trades 数组
        valid_trades = trades[trades[:, 0] >= 0]  # 过滤掉无效交易（date_idx < 0）
        logger.info(f"开始产出交易记录，共 {len(valid_trades)} 笔有效交易（总数组长度: {len(trades)}）")
        code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
        idx_to_code = {idx: code for code, idx in code_to_idx.items()}
        
        # 【流式优化】收集交易记录，按日期分组，以便按日期顺序产出权益数据
        trades_by_date = {}  # {date: [trade_records]}
        trade_count = 0
        
        for trade in trades:
            date_idx = int(trade[0])
            stock_idx = int(trade[1])
            action_code = int(trade[2])
            price = float(trade[3])
            shares = float(trade[4])
            
            if date_idx < 0 or stock_idx < 0:
                continue
            
            date = trading_dates[date_idx]
            stock_code = idx_to_code.get(stock_idx, f"UNKNOWN_{stock_idx}")
            action = "buy" if action_code == 1 else "sell"
            
            trade_record = {
                "date": date,
                "symbol": stock_code,
                "symbol_code": stock_code,
                "action": action,
                "price": price,
                "quantity": shares,
            }
            all_trades_log.append(trade_record)
            
            # 按日期分组交易记录
            if date not in trades_by_date:
                trades_by_date[date] = []
            trades_by_date[date].append(trade_record)
            trade_count += 1
        
        # 7. 按日期顺序产出交易记录和权益数据（流式产出）
        # 这样可以确保前端在回测过程中实时看到权益曲线更新，且数据按日期顺序
        _t_output_start = time.perf_counter()
        for t, current_date in enumerate(trading_dates):
            # 产出该日期的权益数据（优先产出，确保前端能实时看到曲线更新）
            total_value = float(portfolio_value_history[t])
            results_list.append({
                'date': current_date,
                'total_value': total_value,
            })
            yield {
                "type": "daily_equity_engine",
                "data": {
                    "date": current_date,
                    "strategyReturn": total_value
                }
            }
            
            # 产出该日期的所有交易记录
            if current_date in trades_by_date:
                for trade_record in trades_by_date[current_date]:
                    yield {"type": "new_trade_engine", "data": trade_record}
            
            # 【优化】减少日志输出频率，每50天输出一次
            if (t + 1) % 50 == 0:
                logger.debug(f"[STREAM] 已产出 {t + 1}/{len(trading_dates)} 天的权益数据和交易记录")
        
        # 8. 计算最终指标
        if not results_list:
            yield {"type": "error", "data": {"message": "回测未产生任何结果"}}
            return

        results_df = pd.DataFrame(results_list)
        final_metrics = self._calculate_metrics_from_df(results_df, all_trades_log)

        yield {
            "type": "final_metrics",
            "data": final_metrics
        }
        
        # 9. 产出完成信号
        yield {"type": "stream_complete"}
        
        logger.info("流式回测完成")
        
    def _calculate_metrics_from_df(self, results_df: pd.DataFrame, trades_log: List[Dict]) -> Dict:
        """计算回测指标"""
        if results_df.empty:
            return {}
        
        initial_capital = self.initial_capital
        final_value = results_df['total_value'].iloc[-1]
        total_return = (final_value / initial_capital - 1) * 100

        days = len(results_df)
        years = days / 252.0
        annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else total_return

        results_df['cummax'] = results_df['total_value'].cummax()
        results_df['drawdown'] = (results_df['total_value'] - results_df['cummax']) / results_df['cummax']
        max_drawdown = results_df['drawdown'].min() * 100

        daily_returns = results_df['total_value'].pct_change().dropna()
        if len(daily_returns) > 1:
            dr_mean = daily_returns.mean()
            dr_std = daily_returns.std()
            sharpe_ratio = (dr_mean / dr_std) * np.sqrt(252) if dr_std > 0 else 0
            
            downside = daily_returns[daily_returns < 0]
            sortino = (dr_mean / downside.std()) * np.sqrt(252) if len(downside) > 0 and downside.std() > 0 else 0
            volatility = dr_std * np.sqrt(252) * 100
        else:
            sharpe_ratio = 0
            sortino = 0
            volatility = 0

        # 交易统计
        sell_trades = [t for t in trades_log if t.get('action') == 'sell']
        win_trades = sum(1 for t in sell_trades if t.get('profit_loss', 0) > 0)
        win_rate = (win_trades / len(sell_trades)) * 100 if sell_trades else 0
        
        return {
            "totalReturn": round(float(total_return), 2),
            "annualizedReturn": round(float(annualized_return), 2),
            "maxDrawdown": round(float(abs(max_drawdown)), 2),
            "sharpeRatio": round(float(sharpe_ratio), 2),
            "sortinoRatio": round(float(sortino), 2),
            "volatility": round(float(volatility), 2),
            "winRate": round(float(win_rate), 1),
            "tradesCount": len(trades_log),
        }
