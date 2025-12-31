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

    def _load_data_with_polars_streaming(self, start_date: str, end_date: str, 
                                         required_warmup: int = 60) -> Generator:
        """
        流式加载数据（生成器版本），在关键步骤之间 yield 进度更新，避免30秒超时
        
        Yields:
            - 进度更新字典（type="initializing"）
            - 最终结果元组 (price_matrix, stock_codes, trading_dates)
        """
        from config.logger import get_logger
        import json, time
        logger = get_logger(__name__)
        
        # #region agent log
        _t_method_start = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"方法开始","data":{"start":start_date,"end":end_date,"warmup":required_warmup},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"A"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        _progress_update_1 = {
            "type": "initializing",
            "data": {"message": "正在从数据库加载数据...", "progress": 5}
        }
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"准备yield第一个进度更新","data":{"progress":5},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        yield _progress_update_1
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"已yield第一个进度更新","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 计算加载日期范围（包含预热期）
        # #region agent log
        _t_calc_range = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"开始计算日期范围","data":{"start":start_date,"warmup":required_warmup},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"C"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        load_start = pd.to_datetime(start_date) - pd.Timedelta(days=required_warmup)
        load_start_str = load_start.strftime('%Y-%m-%d')
        # #region agent log
        _t_calc_range_end = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"日期范围计算完成","data":{"load_start":load_start_str,"elapsed":_t_calc_range_end-_t_calc_range},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"C"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 获取交易日期
        # #region agent log
        _t_get_dates = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"开始调用get_trading_dates","data":{"start":start_date,"end":end_date},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"C"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        trading_dates = self.data_query.get_trading_dates(start_date, end_date)
        # #region agent log
        _t_get_dates_end = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"get_trading_dates完成","data":{"count":len(trading_dates) if trading_dates else 0,"elapsed":_t_get_dates_end-_t_get_dates},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"C"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        if not trading_dates:
            raise ValueError(f"No trading dates found between {start_date} and {end_date}")
        
        logger.info(f"加载数据: {load_start_str} 到 {end_date} (回测: {start_date} 到 {end_date})")
        
        _progress_update_2 = {
            "type": "initializing",
            "data": {"message": "正在从 LanceDB 加载行情数据...", "progress": 10}
        }
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"准备yield第二个进度更新","data":{"progress":10},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        yield _progress_update_2
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"已yield第二个进度更新","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 检查是否使用 LanceDB
        # #region agent log
        _t_check_lancedb = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"开始检查LanceDB","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"D"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        use_lancedb = hasattr(self.data_query, '_use_lancedb') and self.data_query._use_lancedb
        # #region agent log
        _t_check_lancedb_end = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"LanceDB检查完成","data":{"use_lancedb":use_lancedb,"has_lance_manager":hasattr(self.data_query, 'lance_manager'),"elapsed":_t_check_lancedb_end-_t_check_lancedb},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"D"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        if use_lancedb and hasattr(self.data_query, 'lance_manager'):
            try:
                # 跳过股票池过滤（避免额外的 get_stock_pool 调用，可能导致卡顿）
                # 直接加载所有股票，然后在内存中过滤
                stock_codes_filter = None
                
                _progress_update_3 = {
                    "type": "initializing",
                    "data": {"message": "正在从 LanceDB 查询数据...", "progress": 15}
                }
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"准备yield第三个进度更新","data":{"progress":15},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                yield _progress_update_3
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"已yield第三个进度更新","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                # 加载数据（不传 stock_codes_filter，加载所有股票）
                # #region agent log
                _t_load_lazy = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"开始调用load_to_polars_lazy","data":{"start":load_start_str,"end":end_date},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"A"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                lazy_df = self.data_query.lance_manager.load_to_polars_lazy(
                    start_date=load_start_str,
                    end_date=end_date,
                    stock_codes=None,  # 不传股票池过滤，避免额外的查询
                    columns=['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
                )
                # #region agent log
                _t_load_lazy_end = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"load_to_polars_lazy完成","data":{"elapsed":_t_load_lazy_end-_t_load_lazy},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"A"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                _progress_update_4 = {
                    "type": "initializing",
                    "data": {"message": "正在执行数据库查询...", "progress": 18}
                }
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"准备yield第四个进度更新，然后执行collect","data":{"progress":18},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"B"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                yield _progress_update_4
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"已yield第四个进度更新，开始执行collect","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"A"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                # #region agent log
                _t_collect = time.perf_counter()
                # #endregion
                df = lazy_df.collect()
                # #region agent log
                _t_collect_end = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars_streaming","message":"collect完成","data":{"elapsed":_t_collect_end-_t_collect,"rows":len(df) if not df.is_empty() else 0},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"A"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
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
        
        # 获取唯一的股票代码和日期
        stock_codes = sorted(df['stock_code'].unique().to_list())
        dates = sorted(df['trade_date'].unique().to_list())
        
        yield {
            "type": "initializing",
            "data": {"message": f"正在构建价格矩阵 ({len(dates)} 个交易日, {len(stock_codes)} 只股票)...", "progress": 20}
        }
        
        # 创建价格矩阵
        T = len(dates)
        N = len(stock_codes)
        
        # 【性能优化】使用向量化操作构建价格矩阵，替代双重循环
        # 方法：将 Polars DataFrame 转换为 Pandas，然后使用索引映射一次性构建矩阵
        try:
            # 转换为 Pandas（如果数据量不大，这比循环快得多）
            df_pd = df.to_pandas()
            
            # 创建日期和股票代码的映射索引（用于快速查找）
            date_to_idx = {date: idx for idx, date in enumerate(dates)}
            code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
            
            # 添加索引列
            df_pd['date_idx'] = df_pd['trade_date'].map(date_to_idx)
            df_pd['code_idx'] = df_pd['stock_code'].map(code_to_idx)
            
            # 过滤掉无效的索引（如果日期或代码不在列表中）
            df_pd = df_pd.dropna(subset=['date_idx', 'code_idx'])
            df_pd['date_idx'] = df_pd['date_idx'].astype(int)
            df_pd['code_idx'] = df_pd['code_idx'].astype(int)
            
            # 初始化价格矩阵
            price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
            
            # 向量化填充：使用索引直接赋值（比循环快 10-100 倍）
            price_cols = ['open', 'high', 'low', 'close']
            for i, col in enumerate(price_cols):
                if col in df_pd.columns:
                    # 使用向量化操作，一次性填充所有值
                    valid_mask = df_pd[col].notna()
                    if valid_mask.any():
                        price_matrix[
                            df_pd.loc[valid_mask, 'date_idx'].values,
                            df_pd.loc[valid_mask, 'code_idx'].values,
                            i
                        ] = df_pd.loc[valid_mask, col].values.astype(np.float32)
            
            logger.info(f"✓ 价格矩阵构建完成（向量化方法）: {T} 个交易日, {N} 只股票")
            
        except Exception as e:
            # 回退到原始方法（如果向量化失败）
            logger.warning(f"向量化构建价格矩阵失败，回退到循环方法: {e}")
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
        logger = get_logger(__name__)
        
        # #region agent log
        import json, time
        _t_method_start = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars","message":"开始加载数据","data":{"start":start_date,"end":end_date,"warmup":required_warmup},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
        except: pass
        # #endregion
        
        # 计算加载日期范围（包含预热期）
        load_start = pd.to_datetime(start_date) - pd.Timedelta(days=required_warmup)
        load_start_str = load_start.strftime('%Y-%m-%d')
        
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
            # #region agent log
            _t_load_start = time.perf_counter()
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars","message":"开始一次性加载LanceDB数据","data":{"start":load_start_str,"end":end_date,"total_dates":len(all_trading_dates)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
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
                # #region agent log
                _t_load_end = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars","message":"LanceDB数据加载完成","data":{"elapsed":_t_load_end-_t_load_start,"rows":len(df) if not df.is_empty() else 0},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                if df.is_empty():
                    raise ValueError("No data loaded from LanceDB")
            except Exception as e:
                logger.warning(f"一次性加载失败，回退到DuckDB批量查询: {e}")
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:_load_data_with_polars","message":"LanceDB加载失败，回退到DuckDB","data":{"error":str(e)[:200]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"I"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
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
        
        # 获取唯一的股票代码和日期
        stock_codes = sorted(df['stock_code'].unique().to_list())
        dates = sorted(df['trade_date'].unique().to_list())
        
        # 创建价格矩阵 (T, N, 4) - [open, high, low, close]
        T = len(dates)
        N = len(stock_codes)
        
        # 【性能优化】使用向量化操作构建价格矩阵，替代双重循环
        # 方法：将 Polars DataFrame 转换为 Pandas，然后使用 pivot_table 一次性构建矩阵
        # 这比双重循环快 10-100 倍
        try:
            # 转换为 Pandas（如果数据量不大，这比循环快得多）
            df_pd = df.to_pandas()
            
            # 创建日期和股票代码的映射索引（用于快速查找）
            date_to_idx = {date: idx for idx, date in enumerate(dates)}
            code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
            
            # 添加索引列
            df_pd['date_idx'] = df_pd['trade_date'].map(date_to_idx)
            df_pd['code_idx'] = df_pd['stock_code'].map(code_to_idx)
            
            # 过滤掉无效的索引（如果日期或代码不在列表中）
            df_pd = df_pd.dropna(subset=['date_idx', 'code_idx'])
            df_pd['date_idx'] = df_pd['date_idx'].astype(int)
            df_pd['code_idx'] = df_pd['code_idx'].astype(int)
            
            # 初始化价格矩阵
            price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
            
            # 向量化填充：使用索引直接赋值（比循环快 10-100 倍）
            price_cols = ['open', 'high', 'low', 'close']
            for i, col in enumerate(price_cols):
                if col in df_pd.columns:
                    # 使用向量化操作，一次性填充所有值
                    valid_mask = df_pd[col].notna()
                    if valid_mask.any():
                        price_matrix[
                            df_pd.loc[valid_mask, 'date_idx'].values,
                            df_pd.loc[valid_mask, 'code_idx'].values,
                            i
                        ] = df_pd.loc[valid_mask, col].values.astype(np.float32)
            
            logger.info(f"✓ 价格矩阵构建完成（向量化方法）: {T} 个交易日, {N} 只股票")
            
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
    @jit(nopython=True)
    def _fast_match_loop(
        price_matrix: np.ndarray,  # (T, N, 4) - [open, high, low, close]
        signal_matrix: np.ndarray,  # (T, N) - 0=hold, 1=buy, 2=sell
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
                    if np.isnan(price) or price <= 0:
                        continue
                    
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
            # 在 Numba JIT 函数中，不能使用 Python 类型检查，直接使用 NumPy 数组
            # 预先分配足够大的数组，然后只使用前 N 个元素
            buy_signals_arr = np.empty(N, dtype=np.int64)
            buy_signals_count = 0
            for n in range(N):
                if signal_matrix[t, n] == 1 and positions[n] == 0:  # buy
                    buy_signals_arr[buy_signals_count] = n
                    buy_signals_count += 1
            
            # 限制买入数量
            if max_positions > 0:
                current_positions = np.sum(positions > 0)
                buy_allowance = max_positions - current_positions
                if buy_allowance <= 0:
                    buy_signals_count = 0
                elif buy_signals_count > buy_allowance:
                    buy_signals_count = buy_allowance
            
            # 使用 buy_signals_arr 的前 buy_signals_count 个元素
            buy_signals = buy_signals_arr[:buy_signals_count]
            
            # 执行买入
            if buy_signals_count > 0:
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
                    target_per_stock = cash / buy_signals_count if buy_signals_count > 0 else 0
                
                for i in range(buy_signals_count):
                    n = buy_signals[i]
                    price = opens[n] if not np.isnan(opens[n]) else closes[n]
                    if np.isnan(price) or price <= 0:
                        continue
                
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
                    if not np.isnan(price) and price > 0:
                        portfolio_value += positions[n] * price
            
            cash_history[t] = cash
            portfolio_value_history[t] = portfolio_value
        
        # 截断交易记录
        if trade_count < max_trades:
            trades = trades[:trade_count]
        
        return cash_history, portfolio_value_history, trades
    
    def _convert_signals_to_matrix(self, signals_dict: Dict[str, Dict[str, str]], 
                                   stock_codes: List[str], 
                                   date: str) -> np.ndarray:
        """
        将策略信号字典转换为信号矩阵
        
        Args:
            signals_dict: {stock_code: 'buy'/'sell'/'hold'}
            stock_codes: 股票代码列表
            date: 当前日期（用于日志）
            
        Returns:
            signal_matrix: (N,) - 0=hold, 1=buy, 2=sell
        """
        signal_matrix = np.zeros(len(stock_codes), dtype=np.int32)
        code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
        
        for code, signal in signals_dict.items():
            if code in code_to_idx:
                idx = code_to_idx[code]
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
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"准备yield初始进度更新(0%)","data":{"progress":0},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        yield {
            "type": "initializing",
            "data": {"message": "正在加载数据...", "progress": 0}
        }
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"已yield初始进度更新(0%)","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 1. 加载数据（Polars）- 使用生成器版本，支持进度更新
        # #region agent log
        import json, time
        _t_load_start = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"准备调用_load_data_with_polars","data":{"start":start_date_str,"end":end_date_str,"warmup":required_warmup},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
                f.flush()  # 强制刷新
        except Exception as log_err:
            print(f"[DEBUG] 日志写入失败: {log_err}")
        # #endregion
        try:
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始调用_load_data_with_polars","data":{},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            # 使用生成器版本，在关键步骤之间 yield 进度更新
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始迭代_load_data_with_polars_streaming生成器","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            _iter_count = 0
            for item in self._load_data_with_polars_streaming(
                start_date_str, end_date_str, required_warmup
            ):
                _iter_count += 1
                # #region agent log
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"收到生成器item","data":{"iter":_iter_count,"is_tuple":isinstance(item, tuple),"item_type":type(item).__name__},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                # 检查是否是最终结果（元组）
                if isinstance(item, tuple) and len(item) == 3:
                    # 最终结果
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"收到最终结果，退出循环","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
                    price_matrix, stock_codes, trading_dates = item
                    break
                else:
                    # 进度更新，yield 给前端
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"准备yield进度更新给外层","data":{"item_type":item.get('type') if isinstance(item, dict) else 'unknown'},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
                    yield item
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"已yield进度更新给外层","data":{},"sessionId":"debug-session","runId":"debug-run","hypothesisId":"E"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
            # #region agent log
            _t_load_end = time.perf_counter()
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"_load_data_with_polars返回","data":{"elapsed":_t_load_end-_t_load_start,"shape":list(price_matrix.shape) if price_matrix is not None else None,"stocks":len(stock_codes) if stock_codes else 0,"dates":len(trading_dates) if trading_dates else 0},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
        except Exception as e:
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"数据加载异常","data":{"error":str(e)[:500]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
                    f.flush()
            except: pass
            # #endregion
            logger.error(f"数据加载失败: {e}")
            yield {"type": "error", "data": {"message": f"数据加载失败: {e}"}}
            return

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
        
        # 注意：stock_limit_status 预加载已在 _load_data_with_polars 中完成
        # 这里不再重复预加载，避免浪费时间和资源
        
        # 发送预加载完成进度
        yield {
            "type": "initializing",
            "data": {"message": "辅助数据预加载完成，正在计算技术指标...", "progress": 60}
        }

        # 2. 计算技术指标（GPU/CuPy）
        logger.info("计算技术指标...")
        # #region agent log
        _t_indicator_start = time.perf_counter()
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始计算技术指标","data":{"shape":list(price_matrix.shape) if price_matrix is not None else None},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        try:
            indicator_matrix = self._calculate_indicators_gpu(price_matrix)
            logger.info(f"指标计算完成: {indicator_matrix.shape}")
            # #region agent log
            _t_indicator_end = time.perf_counter()
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"技术指标计算完成(GPU)","data":{"elapsed":_t_indicator_end-_t_indicator_start,"shape":list(indicator_matrix.shape) if indicator_matrix is not None else None},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
            except: pass
            # #endregion
        except Exception as e:
            logger.warning(f"GPU 指标计算失败，回退到 CPU: {e}")
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"GPU计算失败，回退到CPU","data":{"error":str(e)[:200]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
            except: pass
            # #endregion
            _t_cpu_start = time.perf_counter()
            indicator_matrix = self._calculate_indicators_cpu(price_matrix)
            _t_cpu_end = time.perf_counter()
            # #region agent log
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"技术指标计算完成(CPU)","data":{"elapsed":_t_cpu_end-_t_cpu_start,"shape":list(indicator_matrix.shape) if indicator_matrix is not None else None},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"H"}) + "\n")
            except: pass
            # #endregion
        
        # 发送初始化完成进度
        yield {
            "type": "initializing",
            "data": {"message": "技术指标计算完成，准备开始回测...", "progress": 90}
        }
        
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"准备yield backtest_start","data":{"T":T,"N":N},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        yield {
            "type": "backtest_start",
            "data": {"initialCapital": self.initial_capital}
        }
        
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"已yield backtest_start，开始逐日执行","data":{"T":T,"N":N,"dates_count":len(trading_dates)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        # 4. 逐日执行（保持流式输出）
        results_list = []
        all_trades_log = []
        
        # 初始化
        cash = self.initial_capital
        portfolio = {}  # {stock_code: {'shares': ..., 'entry_price': ...}}
        
        # 构建信号矩阵（逐日生成）
        signal_matrix = np.zeros((T, N), dtype=np.int32)
        
        # #region agent log
        try:
            with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"信号矩阵初始化完成，开始循环","data":{"T":T,"N":N},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"J"}) + "\n")
                f.flush()
        except: pass
        # #endregion
        
        for t, current_date in enumerate(tqdm(trading_dates, desc="流式回测进度")):
            if stop_event and stop_event.is_set():
                logger.warning("收到停止信号，结束流式回测")
                return
            
            # #region agent log
            import json, time
            try:
                with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始处理日期","data":{"date":current_date,"t":t,"total":len(trading_dates)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
            except: pass
            # #endregion
            
            try:
                # 获取当日股票池（用于策略）
                # #region agent log
                _t_pool_start = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始获取股票池","data":{"date":current_date,"t":t,"total":len(trading_dates)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                stock_pool = self.data_query.get_stock_pool(current_date)
                # #region agent log
                _t_pool_end = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"获取股票池完成","data":{"date":current_date,"elapsed":_t_pool_end-_t_pool_start,"rows":len(stock_pool) if stock_pool is not None and not stock_pool.empty else 0},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                if stock_pool is None or stock_pool.empty:
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"股票池为空，跳过","data":{"date":current_date},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
                    # 如果没有数据，跳过
                    continue

                # 设置策略运行时上下文
                if hasattr(strategy, "set_runtime_context"):
                    strategy.set_runtime_context(current_date, portfolio, cash)

                # 生成信号
                # #region agent log
                _t_signal_start = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"开始生成信号","data":{"date":current_date},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                try:
                    signals = strategy.generate_signals(current_date, stock_pool, self.data_query)
                except Exception as e:
                    logger.error(f"策略信号生成失败 ({current_date}): {e}", exc_info=True)
                    # #region agent log
                    try:
                        with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"策略信号生成失败","data":{"date":current_date,"error":str(e)[:200]},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                            f.flush()
                    except: pass
                    # #endregion
                    signals = {}
                # #region agent log
                _t_signal_end = time.perf_counter()
                try:
                    with open(r'd:\aquatrade\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"id":f"log_{int(time.time()*1000)}","timestamp":int(time.time()*1000),"location":"optimized_backtest_engine.py:run_backtest_streaming","message":"生成信号完成","data":{"date":current_date,"elapsed":_t_signal_end-_t_signal_start,"signals_count":len(signals)},"sessionId":"debug-session","runId":"perf-debug","hypothesisId":"G"}) + "\n")
                        f.flush()
                except: pass
                # #endregion
                
                # 转换为信号矩阵
                signal_matrix[t, :] = self._convert_signals_to_matrix(signals, stock_codes, current_date)
                
                # 产出交易信号（用于实时显示）
                if signals:
                    for code, signal in signals.items():
                        if signal in ['buy', 'sell']:
                            yield {
                                "type": "signal",
                                "data": {
                                    "date": current_date,
                                    "symbol": code,
                                    "action": signal
                                }
                            }
            except Exception as e:
                logger.error(f"处理日期 {current_date} 时出错: {e}", exc_info=True)
                continue
        
        # 5. 执行快速匹配循环（Numba）
        logger.info("执行快速匹配循环...")
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
        except Exception as e:
            logger.error(f"快速匹配循环失败: {e}", exc_info=True)
            yield {"type": "error", "data": {"message": f"执行失败: {e}"}}
            return
        
        # 6. 转换交易记录并产出
        code_to_idx = {code: idx for idx, code in enumerate(stock_codes)}
        idx_to_code = {idx: code for code, idx in code_to_idx.items()}
        
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
            yield {"type": "new_trade_engine", "data": trade_record}
        
        # 7. 产出每日权益
        for t, current_date in enumerate(trading_dates):
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
