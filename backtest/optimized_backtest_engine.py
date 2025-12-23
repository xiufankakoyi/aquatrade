# backtest/optimized_backtest_engine.py
"""
优化的回测引擎

CHANGED: 修复价格复权逻辑，使用全库最新因子作为基准

主要功能：
1. run_backtest_streaming: 流式回测生成器（支持实时输出）
2. execute_trades: 执行交易逻辑（买入/卖出）
3. _calculate_metrics_from_df: 计算回测指标

性能优化：
- 数据预加载机制（减少数据库 I/O）
- 向量化价格映射生成
- 优化的错误处理和重试机制
- 【修复】正确的前复权计算逻辑：Raw * (CurrentFactor / GlobalLatestFactor)
"""
import pandas as pd
try:
    import cupy as np
except ImportError:
    import numpy as np
from tqdm import tqdm
import asyncio
from typing import AsyncGenerator, Dict, Any, Generator, Tuple, List, Optional
from threading import Event
from datetime import timedelta
import time
import os
from pathlib import Path


class OptimizedBacktestEngine:
    # 默认配置常量（不再依赖 Config）
    DEFAULT_INITIAL_CAPITAL = 1_000_000  # 默认初始资金（元）
    DEFAULT_COMMISSION_RATE = 0.0005  # 默认佣金费率（万分之五）
    DEFAULT_MIN_COMMISSION = 5.0  # 默认最低手续费（元）
    DEFAULT_SELL_TAX = 0.001  # 默认卖出印花税（千分之一，0.1%）
    DEFAULT_BOARD_LOT = 100  # 默认每手股数
    DEFAULT_MAX_POSITIONS = 3  # 默认最大持仓数量
    DEFAULT_POSITION_RATIO = 0.2  # 默认单只股票仓位比例（20%）
    
    def __init__(self, data_query, initial_capital=None, commission_rate=None):
        self.data_query = data_query
        # 从参数或环境变量获取初始资金，否则使用默认值
        if initial_capital is None:
            env_capital = os.getenv('INITIAL_CAPITAL')
            self.initial_capital = float(env_capital) if env_capital else self.DEFAULT_INITIAL_CAPITAL
        else:
            self.initial_capital = initial_capital
        # 从参数或环境变量获取佣金费率，否则使用默认值
        if commission_rate is None:
            env_rate = os.getenv('COMMISSION_RATE')
            self.commission_rate = float(env_rate) if env_rate else self.DEFAULT_COMMISSION_RATE
        else:
            self.commission_rate = commission_rate
        self._portfolio_value_cache = {}
        self.latest_factors = {}  # 存储回测结束时的最新复权因子
        
        # 【新增】可交易性过滤层：缓存 stock_limit_status 数据
        self._limit_status_cache: Optional[pd.DataFrame] = None
        self._limit_status_file_path = None
        # 【新增】过滤统计：记录因各过滤条件被拦截的买入次数
        self._filter_stats = {
            'limit_up_blocked': 0,      # 因涨停(未开板)被拦截
            'limit_down_blocked': 0,    # 因跌停被拦截
            'suspended_blocked': 0,     # 因停牌被拦截
            'total_blocked': 0          # 总拦截次数
        }
        

    def _validate_dates(self, start_date, end_date) -> Tuple[str, str]:
        """(新) 辅助函数：确保日期是字符串"""
        start_date_str = start_date
        end_date_str = end_date
        if isinstance(start_date, pd.Timestamp):
            start_date_str = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, pd.Timestamp):
            end_date_str = end_date.strftime('%Y-%m-%d')
        return start_date_str, end_date_str

    def _apply_qfq(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        【修复核心】计算前复权价格
        公式：前复权价 = 不复权价 * (当日因子 / 最新因子)
        """
        if df is None or df.empty:
            return df
        
        # 必须包含 adj_factor 才能计算
        if 'adj_factor' not in df.columns:
            return df
            
        df = df.copy()
        
        # 1. 获取最新因子
        # 如果没有 self.latest_factors (未初始化)，则无法进行标准 QFQ，回退到使用原始价格或 Post-adj?
        # 这里的策略是：如果找不到最新因子，就假设 最新因子 = 当日因子 (即 Ratio = 1)，保持原始价格
        if not self.latest_factors:
            return df

        # 2. 映射最新因子
        # map 可能会产生 NaN (如果该股票在 latest_factors 中不存在，例如已退市)
        latest_factor_series = df['stock_code'].map(self.latest_factors)
        
        # 3. 处理缺失的最新因子
        # 如果缺失，用当日因子填充 -> Ratio = 1 -> 使用不复权价格
        # 这比使用 1.0 填充更安全，因为因子大小不一
        latest_factor_series.fillna(df['adj_factor'], inplace=True)
        
        # 4. 防止除以零
        latest_factor_series.replace(0, 1.0, inplace=True)
        
        # 5. 计算前复权比率
        qfq_ratio = df['adj_factor'] / latest_factor_series
        
        # 6. 应用比率到价格列（包括所有价格相关的预计算指标）
        # 【核心修复】不仅调整 O/H/L/C，必须同时调整 ma5, ma10, ma20 以及所有价格相关的预计算指标
        price_cols = ['open', 'high', 'low', 'close', 'prev_close', 
                      'ma5', 'ma10', 'ma20', 'ma60',  # 均线指标
                      'ma3_avg_price', 'ma5_avg_price', 'ma10_avg_price']  # 其他价格相关指标
        for col in price_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') * qfq_ratio
                
        return df

    def _handle_corporate_actions(
        self, 
        date: str, 
        portfolio: Dict, 
        cash: float, 
        stock_pool_raw: Optional[pd.DataFrame]
    ) -> Tuple[Dict, float]:
        """
        【核心修复 P1】处理除权除息事件（保守策略）
        
        问题：adj_factor 的变化可能由送股（Split）或分红（Dividend）引起，无法直接区分。
        
        保守策略：
        1. 检测 adj_factor 变化和 Raw Price 变化的比例关系
        2. 如果 Close_T / Close_T-1 ≈ 1 / Factor_Ratio，判定为拆股/送股，调整持仓股数
        3. 否则，判定为分红或其他，直接忽略（保守原则：宁可少算分红，也不错误增加股数）
        
        Args:
            date: 当前日期
            portfolio: 当前持仓
            cash: 当前现金
            stock_pool_raw: 原始（不复权）股票池数据
            
        Returns:
            (更新后的持仓, 更新后的现金)
        """
        if not portfolio or stock_pool_raw is None or stock_pool_raw.empty:
            return portfolio, cash
        
        if 'adj_factor' not in stock_pool_raw.columns:
            return portfolio, cash
        
        new_portfolio = portfolio.copy()
        new_cash = cash
        
        # 获取持仓股票的 adj_factor 和价格
        for stock_code in list(new_portfolio.keys()):
            stock_data = stock_pool_raw[stock_pool_raw['stock_code'] == stock_code]
            if stock_data.empty:
                continue
            
            current_factor = stock_data.iloc[0]['adj_factor']
            current_close = stock_data.iloc[0].get('close')
            current_prev_close = stock_data.iloc[0].get('prev_close')
            
            if pd.isna(current_factor) or current_factor <= 0:
                continue
            
            position = new_portfolio[stock_code]
            entry_factor = position.get('entry_adj_factor', current_factor)  # 记录买入时的因子
            entry_close = position.get('entry_close', current_close)  # 记录买入时的收盘价
            
            # 检测除权除息事件：如果当前因子与买入时因子不同，说明发生了除权除息
            if abs(current_factor - entry_factor) > 1e-6:
                # 计算复权比率
                factor_ratio = current_factor / entry_factor if entry_factor > 0 else 1.0
                
                # 【保守策略】尝试区分送股和分红
                # 送股特征：价格按比例下降，因子按比例上升，价格变化比例 ≈ 1 / 因子变化比例
                is_likely_split = False
                
                if current_close is not None and entry_close is not None and entry_close > 0:
                    price_ratio = current_close / entry_close
                    expected_price_ratio = 1.0 / factor_ratio if factor_ratio > 0 else 1.0
                    
                    # 允许 5% 的误差（考虑市场波动）
                    price_diff_ratio = abs(price_ratio - expected_price_ratio) / expected_price_ratio
                    
                    # 如果价格变化比例与因子变化比例匹配，判定为送股
                    if factor_ratio > 1.0 and price_diff_ratio < 0.05:
                        is_likely_split = True
                
                # 处理送股：按比例增加持仓股数
                if is_likely_split and factor_ratio > 1.0:
                    current_shares = position.get('shares', 0)
                    if current_shares > 0:
                        # 送股：持仓股数按比例增加
                        new_shares = int(current_shares * factor_ratio)
                        position['shares'] = new_shares
                        # 更新持仓成本价（保持不变，因为送股不影响成本）
                        # entry_price 保持不变
                        from utils.logger import get_logger
                        logger = get_logger(__name__)
                        logger.info(
                            f"[{date}] {stock_code} 送股事件：因子 {entry_factor:.4f} -> {current_factor:.4f}, "
                            f"持仓 {current_shares} -> {new_shares} 股"
                        )
                
                # 处理分红：保守策略 - 直接忽略
                # 原因：
                # 1. 无法准确区分分红和送股（仅靠 adj_factor 不够）
                # 2. 错误地将分红当作送股会导致股数虚增，人为放大收益
                # 3. 保守原则：宁可少算分红收益，也不错误增加股数
                # TODO: 如果后续有 dividend_yield 或专门的除权除息表，可以精确处理分红
                
                # 更新持仓的 adj_factor 和收盘价记录
                position['entry_adj_factor'] = current_factor
                if current_close is not None:
                    position['entry_close'] = current_close
        
        return new_portfolio, new_cash

    def _load_limit_status_data(self, date: str) -> Optional[pd.DataFrame]:
        """
        【新增】加载指定日期的股票涨跌停和停牌状态数据
        
        Args:
            date: 交易日期字符串
            
        Returns:
            DataFrame with columns: stock_code, trade_date, is_limit_up, is_limit_down, is_opened, is_suspended
            如果文件不存在或加载失败，返回 None
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        # 确定 parquet 文件路径
        if self._limit_status_file_path is None:
            # 优先从 data_query 获取 parquet_dir，否则使用默认路径
            parquet_dir = getattr(self.data_query, 'parquet_dir', None)
            if parquet_dir is None:
                parquet_dir = os.getenv('PARQUET_DIR', 'parquet_data')
            
            limit_status_path = Path(parquet_dir) / 'stock_limit_status.parquet'
            self._limit_status_file_path = str(limit_status_path)
        
        # 检查文件是否存在
        if not os.path.exists(self._limit_status_file_path):
            logger.warning(f"stock_limit_status.parquet 文件不存在: {self._limit_status_file_path}，跳过可交易性过滤")
            return None
        
        try:
            # 如果已缓存全部数据，直接过滤
            if self._limit_status_cache is not None:
                date_df = self._limit_status_cache[
                    self._limit_status_cache['trade_date'] == date
                ]
                return date_df if not date_df.empty else None
            
            # 否则，尝试加载指定日期的数据
            # 使用 DuckDB 或 pandas 读取（优先使用 DuckDB，性能更好）
            try:
                import duckdb
                conn = duckdb.connect()
                parquet_str = self._limit_status_file_path.replace('\\', '/')
                query = f"""
                    SELECT stock_code, trade_date, is_limit_up, is_limit_down, is_opened, is_suspended
                    FROM parquet_scan('{parquet_str}')
                    WHERE trade_date = '{date}'
                """
                result = conn.execute(query).df()
                conn.close()
                
                if not result.empty:
                    return result
                else:
                    return None
            except ImportError:
                # 如果没有 duckdb，使用 pandas 读取
                limit_status_df = pd.read_parquet(self._limit_status_file_path)
                date_df = limit_status_df[limit_status_df['trade_date'] == date]
                return date_df if not date_df.empty else None
                
        except Exception as e:
            logger.warning(f"加载 stock_limit_status 数据失败 ({date}): {e}，跳过可交易性过滤")
            return None
    
    def _load_latest_factors_robust(self):
        """
        鲁棒方法加载最新复权因子
        支持并行环境，使用数据查询方法而非直接访问连接
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        try:
            # 【关键修复】使用数据查询方法而非直接访问连接，支持并行环境
            # 优先使用数据查询的 _query_df 方法，避免直接访问可能不稳定的连接
            
            # 方法1：尝试使用数据查询方法获取最新因子
            try:
                # 获取最新交易日
                latest_date_query = "SELECT MAX(trade_date) AS max_date FROM stock_daily"
                latest_date_df = self.data_query._query_df(latest_date_query, None)
                
                if latest_date_df.empty or latest_date_df.iloc[0]['max_date'] is None:
                    logger.warning("⚠️ 警告：未能找到最新交易日")
                    return {}
                
                latest_date = latest_date_df.iloc[0]['max_date']
                
                # 获取最新交易日的所有复权因子
                factors_query = """
                    SELECT stock_code, adj_factor 
                    FROM stock_daily 
                    WHERE trade_date = ? AND adj_factor IS NOT NULL
                """
                factors_df = self.data_query._query_df(factors_query, [latest_date])
                
                factors: Dict[str, float] = {}
                for _, row in factors_df.iterrows():
                    try:
                        code = str(row['stock_code'])
                        factor = float(row['adj_factor'])
                        if factor > 0:  # 确保因子有效
                            factors[code] = factor
                    except (TypeError, ValueError, KeyError):
                        continue
                
                if factors:
                    logger.info(f"✅ 成功加载 {len(factors)} 个股票的复权因子（最新日期: {latest_date}）")
                    return factors
                else:
                    logger.warning("⚠️ 警告：未能加载任何复权因子")
                    return {}
                    
            except Exception as method1_err:
                logger.warning(f"⚠️ 使用数据查询方法加载因子失败，尝试备用方法: {method1_err}")
                
                # 方法2：备用方法 - 直接访问连接（如果可用）
                conn = getattr(self.data_query, "conn", None)
                if conn is None:
                    logger.warning("⚠️ 警告：数据查询对象没有可用连接")
                    return {}
                
                try:
                    # 获取最新交易日
                    latest_date_query = "SELECT MAX(trade_date) FROM stock_daily"
                    cursor = conn.execute(latest_date_query)
                    latest_date_row = cursor.fetchone()
                    latest_date = latest_date_row[0] if latest_date_row else None
                    
                    if not latest_date:
                        logger.warning("⚠️ 警告：未能找到最新交易日")
                        return {}
                    
                    # 获取最新交易日的所有复权因子
                    fallback_rows = conn.execute(
                        "SELECT stock_code, adj_factor FROM stock_daily WHERE trade_date = ? AND adj_factor IS NOT NULL",
                        (latest_date,)
                    ).fetchall()
                    
                    factors: Dict[str, float] = {}
                    for code, factor in fallback_rows:
                        try:
                            if factor is not None and float(factor) > 0:
                                factors[str(code)] = float(factor)
                        except (TypeError, ValueError):
                            continue
                    
                    if factors:
                        logger.info(f"✅ 使用备用方法加载 {len(factors)} 个股票的复权因子（最新日期: {latest_date}）")
                        return factors
                    else:
                        logger.warning("⚠️ 警告：备用方法未能加载任何复权因子")
                        return {}
                        
                except Exception as method2_err:
                    logger.error(f"❌ 备用方法也失败: {method2_err}")
                    return {}
            
        except Exception as e:
            logger.error(f"❌ 加载复权因子时发生未知错误: {e}")
            import traceback
            traceback.print_exc()
            return {}

# --- 【【第2步 新增】】: 真·流式回测函数 ---
    def run_backtest_streaming(self, start_date, end_date, strategy, stop_event: Optional[Event] = None) -> Generator[Dict[str, Any], None, None]:
        """
        CHANGED: 真·流式回测生成器（优化版本）
        """
        from utils.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info(f"开始【流式】回测: {start_date} 到 {end_date}")
        
        # CHANGED: 输入验证
        start_date_str, end_date_str = self._validate_dates(start_date, end_date)
        
        # CHANGED: 验证日期顺序
        if start_date_str > end_date_str:
            error_msg = f"开始日期 ({start_date_str}) 不能晚于结束日期 ({end_date_str})"
            logger.error(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return
        
        # 1. 获取数据库全局交易日范围，并根据需要调整起止日期
        try:
            all_dates = self.data_query.get_trading_dates()
        except Exception as e:
            logger.error(f"获取全局交易日期失败: {e}")
            yield {"type": "error", "data": {"message": f"获取交易日期失败: {e}"}}
            return

        if not all_dates:
            error_msg = "数据库中没有交易日数据。请先导入股票数据到数据库。"
            logger.error(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return

        db_start, db_end = all_dates[0], all_dates[-1]

        # 情况 1：请求区间完全在数据库范围之外（晚于或早于全部数据），直接报错
        if start_date_str > db_end:
            error_msg = (
                f"请求区间（{start_date_str} 到 {end_date_str}）晚于数据库最后日期 {db_end}，"
                f"请先导入更新的数据，或选择不晚于 {db_end} 的时间段。"
            )
            logger.warning(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return
        if end_date_str < db_start:
            error_msg = (
                f"请求区间（{start_date_str} 到 {end_date_str}）早于数据库最早日期 {db_start}，"
                f"请先导入更早的数据，或选择不早于 {db_start} 的时间段。"
            )
            logger.warning(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return

        # 情况 2：有交集，但一侧越界 -> 自动夹在数据库范围内
        original_start, original_end = start_date_str, end_date_str
        if start_date_str < db_start:
            start_date_str = db_start
        if end_date_str > db_end:
            end_date_str = db_end

        if (original_start, original_end) != (start_date_str, end_date_str):
            logger.warning(
                f"请求区间 {original_start}~{original_end} 超出数据库范围，"
                f"已自动调整为 {start_date_str}~{end_date_str} 再进行回测。"
            )

        # 2. 获取实际用于回测的交易日期
        try:
            trading_dates = self.data_query.get_trading_dates(start_date_str, end_date_str)
        except Exception as e:
            logger.error(f"获取交易日期失败: {e}")
            yield {"type": "error", "data": {"message": f"获取交易日期失败: {e}"}}
            return

        if not trading_dates:
            error_msg = (
                f"在自动调整后的区间（{start_date_str} 到 {end_date_str}）内仍未找到交易日数据，"
                f"请检查数据库是否已正确导入行情。"
            )
            logger.error(error_msg)
            yield {"type": "error", "data": {"message": error_msg}}
            return
        
        logger.info(f"回测期间共 {len(trading_dates)} 个交易日")

        # 【核心修复】使用鲁棒方法获取全库最新的复权因子
        self.latest_factors = self._load_latest_factors_robust()
        
        if not self.latest_factors:
            logger.warning("⚠️ 警告：未能加载基准因子，将回退到使用原始价格（不复权）")

        # CHANGED: 预加载回测数据（可选优化）
        max_preload_days = int(os.getenv("MAX_PRELOAD_DAYS", "600"))
        use_preload = (
            os.getenv("DISABLE_PRELOAD", "0") != "1"
            and len(trading_dates) <= max_preload_days
        )
        if use_preload:
            try:
                logger.info("开始预加载回测数据...")
                # 【修复4】从策略获取预热期，避免硬编码
                # 如果策略需要 MA60/MA120 等指标，需要更多预热数据
                required_warmup = getattr(strategy, 'warmup_days', 60)  # 默认60天，覆盖MA60
                if required_warmup < 30:
                    required_warmup = 30  # 至少30天，覆盖MA20/MA30
                load_start_date = pd.to_datetime(start_date_str) - timedelta(days=required_warmup)
                load_start_date_str = load_start_date.strftime('%Y-%m-%d')
                logger.info(f"数据加载开始日期提前 {required_warmup} 天: {load_start_date_str} (回测仍从 {start_date_str} 开始)")
                self.data_query.preload_backtest_data(load_start_date_str, end_date_str)
                logger.info("数据预加载完成")
            except Exception as e:
                logger.warning(f"数据预加载失败，将使用逐日查询: {e}")
                use_preload = False

        # 2. 初始化账户
        portfolio = {}
        cash = self.initial_capital
        results_list = []
        all_trades_log = []
        
        # 【新增】重置过滤统计
        self._filter_stats = {
            'limit_up_blocked': 0,
            'limit_down_blocked': 0,
            'suspended_blocked': 0,
            'total_blocked': 0
        }
        
        # 【修复3】待执行的信号队列（解决未来函数问题：今日出信号，明日开盘买入）
        pending_signals: Dict[str, str] = {}  # {stock_code: signal}
        
        # 3. 【产出】开始信号
        yield {
            "type": "backtest_start",
            "data": {"initialCapital": self.initial_capital}
        }
        
        # 4. 【【真·流式循环】】
        for idx, current_date in enumerate(tqdm(trading_dates, desc="流式回测进度"), 1):
            if stop_event and stop_event.is_set():
                logger.warning("⚠️ 收到停止信号，结束流式回测。")
                return
            
            try:
                day_start = time.time()

                # 4a. 获取当日股票池
                t0 = time.time()
                if use_preload:
                    stock_pool_raw = self.data_query.get_stock_pool_from_preloaded(current_date)
                    if stock_pool_raw is None:
                        stock_pool_raw = self.data_query.get_stock_pool(current_date)
                else:
                    stock_pool_raw = self.data_query.get_stock_pool(current_date)
                
                # 【核心修复】分离信号层和交易层的价格使用
                # 1. 保存原始（不复权）股票池，用于交易撮合和资金扣款
                stock_pool_for_trading = stock_pool_raw.copy() if stock_pool_raw is not None and not stock_pool_raw.empty else None
                
                # 2. 对股票池应用前复权，用于信号生成（保证技术指标连续）
                stock_pool = stock_pool_raw
                if stock_pool is not None and not stock_pool.empty:
                    # 验证 adj_factor
                    if 'adj_factor' in stock_pool.columns:
                        # 【核心修复】应用正确的前复权逻辑（仅用于信号生成）
                        stock_pool = self._apply_qfq(stock_pool)
                    else:
                        logger.warning(f"{current_date}: stock_pool 中缺少 adj_factor 列，无法进行复权转换")
                
                t_db = time.time() - t0

                # 设置策略运行时上下文
                if hasattr(strategy, "set_runtime_context"):
                    strategy.set_runtime_context(current_date, portfolio, cash)

                # 4b. 生成当日信号
                t1 = time.time()
                try:
                    signals = strategy.generate_signals(current_date, stock_pool, self.data_query)
                except Exception as e:
                    logger.error(f"策略信号生成失败 ({current_date}): {e}")
                    signals = {}
                t_sig = time.time() - t1

                # 【修复逻辑】检查策略是否需要延迟执行信号
                # 如果策略明确标记 delay_signal_execution=True，则延迟到下一交易日
                # 否则默认当日执行（因为大多数策略基于昨日或更早的数据）
                delay_execution = getattr(strategy, 'delay_signal_execution', False)
                
                t_exec = time.time()
                daily_trades = []
                
                if delay_execution:
                    # 延迟执行模式：今日出信号，明日开盘买入（适用于基于当日收盘数据的策略）
                    pending_signals = signals.copy()
                    # 执行上一交易日产生的信号
                    if pending_signals:
                        price_map_exec: Dict[str, Dict[str, float]] = {}
                        stock_codes_needed_exec = set(pending_signals.keys()) | set(portfolio.keys())
                        # 【核心修复】使用原始（不复权）价格进行交易撮合
                        pool_for_price = stock_pool_for_trading if stock_pool_for_trading is not None and not stock_pool_for_trading.empty else stock_pool
                        if stock_codes_needed_exec and pool_for_price is not None and not pool_for_price.empty:
                            mask = pool_for_price['stock_code'].isin(stock_codes_needed_exec)
                            if mask.any():
                                cols = ['stock_code']
                                if 'open' in pool_for_price.columns:
                                    cols.append('open')
                                if 'close' in pool_for_price.columns:
                                    cols.append('close')
                                if 'limit_down' in pool_for_price.columns:
                                    cols.append('limit_down')
                                
                                price_df = pool_for_price.loc[mask, cols].drop_duplicates(subset=['stock_code'])
                                
                                codes = price_df['stock_code'].to_numpy()
                                opens = price_df['open'].to_numpy() if 'open' in price_df.columns else None
                                closes = price_df['close'].to_numpy() if 'close' in price_df.columns else None
                                limit_downs = price_df['limit_down'].to_numpy() if 'limit_down' in price_df.columns else None

                                for i, code in enumerate(codes):
                                    o = opens[i] if opens is not None else None
                                    c = closes[i] if closes is not None else None
                                    if o is None: o = c
                                    if c is None: c = o
                                    # 【核心修复】使用原始（不复权）价格进行交易撮合和资金扣款
                                    price_map_exec[str(code)] = {
                                        'open': float(o) if o is not None else None,
                                        'close': float(c) if c is not None else None,
                                    }
                                    # 【核心修复】保留 limit_down 用于撮合校验
                                    if limit_downs is not None:
                                        price_map_exec[str(code)]['limit_down'] = float(limit_downs[i]) if not pd.isna(limit_downs[i]) else None
                        
                        try:
                            portfolio, cash, daily_trades = self.execute_trades(
                                current_date, pending_signals, portfolio, cash, price_map_exec, strategy,
                                stock_pool_raw=stock_pool_for_trading
                            )
                        except Exception as e:
                            logger.error(f"执行上一交易日信号失败 ({current_date}): {e}")
                            daily_trades = []
                        pending_signals = {}
                else:
                    # 默认模式：当日执行信号（适用于基于昨日或更早数据的策略）
                    # 例如：1.2日基于12.31的数据生成信号，立即在1.2日执行买入
                    if signals:
                        # 准备价格映射（使用当日开盘价执行交易）
                        price_map_exec: Dict[str, Dict[str, float]] = {}
                        stock_codes_needed_exec = set(signals.keys()) | set(portfolio.keys())
                        # 【核心修复】使用原始（不复权）价格进行交易撮合
                        pool_for_price = stock_pool_for_trading if stock_pool_for_trading is not None and not stock_pool_for_trading.empty else stock_pool
                        if stock_codes_needed_exec and pool_for_price is not None and not pool_for_price.empty:
                            mask = pool_for_price['stock_code'].isin(stock_codes_needed_exec)
                            if mask.any():
                                cols = ['stock_code']
                                if 'open' in pool_for_price.columns:
                                    cols.append('open')
                                if 'close' in pool_for_price.columns:
                                    cols.append('close')
                                if 'limit_down' in pool_for_price.columns:
                                    cols.append('limit_down')
                                
                                price_df = pool_for_price.loc[mask, cols].drop_duplicates(subset=['stock_code'])
                                
                                codes = price_df['stock_code'].to_numpy()
                                opens = price_df['open'].to_numpy() if 'open' in price_df.columns else None
                                closes = price_df['close'].to_numpy() if 'close' in price_df.columns else None
                                limit_downs = price_df['limit_down'].to_numpy() if 'limit_down' in price_df.columns else None

                                for i, code in enumerate(codes):
                                    o = opens[i] if opens is not None else None
                                    c = closes[i] if closes is not None else None
                                    if o is None: o = c
                                    if c is None: c = o
                                    # 【核心修复】使用原始（不复权）价格进行交易撮合和资金扣款
                                    price_map_exec[str(code)] = {
                                        'open': float(o) if o is not None else None,
                                        'close': float(c) if c is not None else None,
                                    }
                                    # 【核心修复】保留 limit_down 用于撮合校验
                                    if limit_downs is not None:
                                        price_map_exec[str(code)]['limit_down'] = float(limit_downs[i]) if not pd.isna(limit_downs[i]) else None
                        
                        try:
                            portfolio, cash, daily_trades = self.execute_trades(
                                current_date, signals, portfolio, cash, price_map_exec, strategy,
                                stock_pool_raw=stock_pool_for_trading
                            )
                        except Exception as e:
                            logger.error(f"执行当日信号失败 ({current_date}): {e}")
                            daily_trades = []
                t_exec_duration = time.time() - t_exec

                # 4d. 处理除权除息事件（在市值计算之前）
                # 【核心修复】检测并处理除权除息事件
                portfolio, cash = self._handle_corporate_actions(
                    current_date, portfolio, cash, stock_pool_for_trading
                )
                
                # 4e. 准备价格映射（用于市值计算，必须使用原始收盘价）
                t2 = time.time()
                price_map: Dict[str, Dict[str, float]] = {}
                stock_codes_needed = set(portfolio.keys())  # 只需要持仓股票的价格用于市值计算
                # 【核心修复 P0】市值计算必须使用原始价格（Raw Price）
                # 持仓股数是真实的物理股数，必须乘以真实收盘价，这才是账户里真金白银的钱
                pool_for_market_value = stock_pool_for_trading if stock_pool_for_trading is not None and not stock_pool_for_trading.empty else stock_pool
                if stock_codes_needed and pool_for_market_value is not None and not pool_for_market_value.empty:
                    mask = pool_for_market_value['stock_code'].isin(stock_codes_needed)
                    if mask.any():
                        cols = ['stock_code']
                        if 'open' in pool_for_market_value.columns:
                            cols.append('open')
                        if 'close' in pool_for_market_value.columns:
                            cols.append('close')
                        
                        price_df = pool_for_market_value.loc[mask, cols].drop_duplicates(subset=['stock_code'])
                        
                        codes = price_df['stock_code'].to_numpy()
                        opens = price_df['open'].to_numpy() if 'open' in price_df.columns else None
                        closes = price_df['close'].to_numpy() if 'close' in price_df.columns else None

                        for i, code in enumerate(codes):
                            o = opens[i] if opens is not None else None
                            c = closes[i] if closes is not None else None
                            if o is None: o = c
                            if c is None: c = o
                            # 【核心修复 P0】市值计算必须使用原始价格（Raw Price）
                            # Market Value = Real Shares * Raw Close Price
                            price_map[str(code)] = {
                                'open': float(o) if o is not None else None,
                                'close': float(c) if c is not None else None,
                            }
                t_price = time.time() - t2

                # 记录单日耗时拆分，方便分析瓶颈
                day_total = time.time() - day_start
                pool_rows = 0 if stock_pool is None else len(stock_pool)
                logger.info(
                    f"[BT][PROFILE] {current_date} "
                    f"pool={pool_rows} rows, "
                    f"db+qfq={t_db*1000:.1f}ms, "
                    f"signal={t_sig*1000:.1f}ms, "
                    f"price_map={t_price*1000:.1f}ms, "
                    f"exec_trades={t_exec_duration*1000:.1f}ms, "
                    f"total={day_total*1000:.1f}ms"
                )
                
                # 4e. 【产出】交易
                if daily_trades:
                    all_trades_log.extend(daily_trades)
                    for trade in daily_trades:
                        yield {"type": "new_trade_engine", "data": trade}
                
                # 4f. 计算当日市值
                portfolio_value = 0
                if portfolio:
                    def get_position_price(code, action='sell'):
                        price_data = price_map.get(code)
                        if price_data is None:
                            return position.get('entry_price')
                        if isinstance(price_data, dict):
                            # 简单策略：优先 close
                            return price_data.get('close') or price_data.get('open')
                        return price_data

                    for stock_code, position in portfolio.items():
                        current_price = get_position_price(stock_code, 'sell')
                        if current_price is None:
                            current_price = position.get('entry_price', 0)
                        shares = position.get('shares', 0)
                        try:
                            portfolio_value += shares * current_price
                        except TypeError:
                            continue

                total_value = portfolio_value + cash
                
                # 4g. 记录结果
                results_list.append({
                    'date': current_date,
                    'total_value': total_value,
                })

                # 4h. 【产出】每日更新
                yield {
                    "type": "daily_equity_engine",
                    "data": {
                        "date": current_date,
                        "strategyReturn": total_value
                    }
                }
                
            except Exception as e:
                logger.error(f"流式回测日期 {current_date} 时出错: {e}", exc_info=True)
                last_value = results_list[-1]['total_value'] if results_list else self.initial_capital
                results_list.append({'date': current_date, 'total_value': last_value})
                continue
        
        # 6. 【产出】最终指标
        if not results_list:
            yield {"type": "error", "data": {"message": "回测未产生任何结果"}}
            return

        results_df = pd.DataFrame(results_list)
        final_metrics = self._calculate_metrics_from_df(results_df, all_trades_log)

        yield {
            "type": "final_metrics",
            "data": final_metrics
        }
        
        # 7. 【产出】完成信号
        yield {"type": "stream_complete"}
        
        # 【新增】输出可交易性过滤统计信息
        logger.info("=== 可交易性过滤统计 ===")
        logger.info(f"因涨停(未开板)被拦截: {self._filter_stats['limit_up_blocked']} 次")
        logger.info(f"因跌停被拦截: {self._filter_stats['limit_down_blocked']} 次")
        logger.info(f"因停牌被拦截: {self._filter_stats['suspended_blocked']} 次")
        logger.info(f"总拦截次数: {self._filter_stats['total_blocked']} 次")
        
        if use_preload:
            self.data_query.clear_preloaded_data()
    # --- 【【新增结束】】 ---

    def _cached_calculate_portfolio_value(self, date, portfolio, stock_pool):
        """(此函数也需要修复价格获取)"""
        if not portfolio: return 0
        cache_key = f"{date}_{hash(frozenset(portfolio.keys()))}"
        if cache_key in self._portfolio_value_cache:
            return self._portfolio_value_cache[cache_key]
        
        total_value = 0
        price_cache = {}
        
        # 1. 尝试从 stock_pool 获取价格 (stock_pool 应该已经是前复权过的)
        for stock_code, position in portfolio.items():
            stock_data = stock_pool[stock_pool['stock_code'] == stock_code]
            if not stock_data.empty:
                current_price = stock_data.iloc[0]['close']
                total_value += position['shares'] * current_price
                price_cache[stock_code] = current_price
        
        # 2. 获取缺失股票的价格
        missing_stocks = set(portfolio.keys()) - set(price_cache.keys())
        if missing_stocks:
            try:
                # 批量查询
                if hasattr(self.data_query, 'get_batch_stock_history'):
                    missing_list = list(missing_stocks)
                    # 获取原始数据
                    batch_history = self.data_query.get_batch_stock_history(
                        missing_list, date, date, columns=['stock_code', 'close', 'adj_factor']
                    )
                    if not batch_history.empty:
                        # 【核心修复】应用前复权
                        batch_history = self._apply_qfq(batch_history)
                        
                        for stock_code in missing_list:
                            stock_data = batch_history[batch_history['stock_code'] == stock_code]
                            if not stock_data.empty:
                                current_price = stock_data.iloc[0]['close']
                                total_value += portfolio[stock_code]['shares'] * current_price
                                price_cache[stock_code] = current_price
            except Exception as e:
                from utils.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"批量查询股票历史数据失败: {e}")

        self._portfolio_value_cache[cache_key] = total_value
        return total_value
    
    def execute_trades(
        self, 
        date: str, 
        signals: Dict[str, str], 
        portfolio: Dict, 
        cash: float, 
        price_map: Dict[str, float],
        strategy=None,
        stock_pool_raw: Optional[pd.DataFrame] = None
    ) -> Tuple[Dict, float, List[Dict]]:
        """
        执行交易
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)
        
        if cash < 0: cash = 0.0
        portfolio = portfolio.copy() if portfolio else {}
        price_map = price_map if price_map else {}
        
        new_portfolio = portfolio.copy()
        daily_trades = []
        
        # FIFO 队列构建
        fifo_positions = {}
        for stock_code, pos in portfolio.items():
            if stock_code not in fifo_positions: fifo_positions[stock_code] = []
            fifo_positions[stock_code].append({
                'date': pos.get('entry_date', date),
                'price': pos.get('entry_price', 0),
                'quantity': pos.get('shares', 0),
                'entry_date': pos.get('entry_date', date)
            })

        def resolve_price(stock_code: str, action: str) -> Optional[float]:
            """
            【修复3】价格解析：买入使用开盘价，卖出使用开盘价（避免偷价）
            """
            price_data = price_map.get(stock_code)
            if price_data is None: return None
            
            price = None
            if isinstance(price_data, dict):
                # 【修复3】买入和卖出都优先使用开盘价（避免使用收盘价偷价）
                # 这符合"今日出信号，明日开盘买入"的逻辑
                price = price_data.get("open") or price_data.get("close")
            else:
                price = price_data
            return price

        # === 1. 处理卖出 ===
        for stock_code in list(new_portfolio.keys()):
            if stock_code in signals and signals[stock_code] == 'sell' and stock_code in price_map:
                try:
                    position = new_portfolio[stock_code]
                    current_price = resolve_price(stock_code, 'sell')
                    if current_price is None or current_price <= 0: continue
                    
                    # 【核心修复 C】跌停板风控：检查是否跌停，跌停时禁止卖出
                    price_data = price_map.get(stock_code)
                    if isinstance(price_data, dict):
                        limit_down_price = price_data.get('limit_down')
                        if limit_down_price is not None and current_price <= limit_down_price:
                            logger.warning(f"[{date}] {stock_code} 跌停锁死（当前价 {current_price:.2f} <= 跌停价 {limit_down_price:.2f}），无法卖出")
                            self._filter_stats['limit_down_blocked'] += 1
                            self._filter_stats['total_blocked'] += 1
                            continue  # 禁止交易
                    
                    # T+1 检查
                    entry_date = position.get('entry_date')
                    if entry_date and entry_date >= date: continue

                    shares = position.get('shares', 0)
                    BOARD_LOT = int(os.getenv('BOARD_LOT', self.DEFAULT_BOARD_LOT))
                    shares = (shares // BOARD_LOT) * BOARD_LOT
                    if shares < BOARD_LOT: continue
                    
                    # 【修复1】计算佣金
                    commission_base = shares * current_price * self.commission_rate
                    min_commission = float(os.getenv('MIN_COMMISSION', self.DEFAULT_MIN_COMMISSION))
                    commission = max(commission_base, min_commission)
                    # 【修复1】计算印花税（卖出时收取，A股规则）
                    sell_tax_rate = float(os.getenv('SELL_TAX', self.DEFAULT_SELL_TAX))  # 默认千分之一
                    tax = shares * current_price * sell_tax_rate
                    # 【修复1】卖出获得的现金要减去佣金和印花税
                    sell_amount = shares * current_price - commission - tax
                    cash += sell_amount
                    
                    # FIFO 匹配
                    entry_price = position.get('entry_price', 0)
                    entry_date = position.get('entry_date', date)
                    if stock_code in fifo_positions and fifo_positions[stock_code]:
                        fifo_positions[stock_code].sort(key=lambda x: x['date'])
                        matched = fifo_positions[stock_code].pop(0)
                        entry_price = matched['price']
                        entry_date = matched['entry_date']
                    
                    # 收益计算
                    holding_days = 0
                    if entry_date and entry_date != date:
                        try:
                            from datetime import datetime
                            d1 = datetime.strptime(entry_date, '%Y-%m-%d')
                            d2 = datetime.strptime(date, '%Y-%m-%d')
                            holding_days = (d2 - d1).days
                        except: pass
                    
                    profit_loss = (current_price - entry_price) * shares
                    roi = (profit_loss / (entry_price * shares)) * 100 if entry_price > 0 else 0
                    
                    del new_portfolio[stock_code]
                    
                    daily_trades.append({
                        "date": date,
                        "symbol": stock_code,
                        "symbol_code": stock_code,
                        "action": "sell",
                        "price": current_price,
                        "quantity": shares,
                        "commission": commission,
                        "tax": tax,  # 【修复1】记录印花税
                        "entry_date": entry_date,
                        "exit_date": date,
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "profit_loss": profit_loss,
                        "roi": roi,
                        "holding_days": holding_days,
                        "position_id": position.get('position_id')
                    })
                except Exception as e:
                    logger.error(f"卖出失败 {stock_code}: {e}")

        # === 2. 处理买入 ===
        buy_signals = [code for code, signal in signals.items() if signal == 'buy']
        
        # 【新增】可交易性过滤层：过滤掉不可交易的股票
        if buy_signals:
            limit_status_df = self._load_limit_status_data(date)
            if limit_status_df is not None and not limit_status_df.empty:
                # 创建状态映射字典，提高查找效率
                status_map = {}
                for _, row in limit_status_df.iterrows():
                    code = str(row['stock_code'])
                    status_map[code] = {
                        'is_limit_up': bool(row.get('is_limit_up', 0)),
                        'is_limit_down': bool(row.get('is_limit_down', 0)),
                        'is_opened': bool(row.get('is_opened', 0)),
                        'is_suspended': bool(row.get('is_suspended', 0))
                    }
                
                # 过滤逻辑：
                # 1. 过滤涨停且未开板：is_limit_up=True 且 is_opened=False
                # 2. 过滤跌停：is_limit_down=True
                # 3. 过滤停牌：is_suspended=True
                # 4. 允许涨停但开过板：is_limit_up=True 且 is_opened=True（可以交易）
                filtered_buy_signals = []
                for code in buy_signals:
                    code_str = str(code)
                    if code_str not in status_map:
                        # 如果找不到状态数据，默认允许交易（保守策略）
                        filtered_buy_signals.append(code)
                        continue
                    
                    status = status_map[code_str]
                    blocked = False
                    block_reason = None
                    
                    # 检查停牌
                    if status['is_suspended']:
                        blocked = True
                        block_reason = 'suspended'
                        self._filter_stats['suspended_blocked'] += 1
                    
                    # 检查跌停
                    elif status['is_limit_down']:
                        blocked = True
                        block_reason = 'limit_down'
                        self._filter_stats['limit_down_blocked'] += 1
                    
                    # 检查涨停（未开板）
                    elif status['is_limit_up'] and not status['is_opened']:
                        blocked = True
                        block_reason = 'limit_up'
                        self._filter_stats['limit_up_blocked'] += 1
                    
                    # 涨停但开过板：允许交易（is_limit_up=True 且 is_opened=True）
                    # 这种情况不需要特殊处理，直接通过
                    
                    if not blocked:
                        filtered_buy_signals.append(code)
                    else:
                        self._filter_stats['total_blocked'] += 1
                
                buy_signals = filtered_buy_signals
        
        # 【修复2+用户需求】仓位管理：策略参数优先，未提供则全仓买入所有信号
        # 检查策略是否提供了仓位管理参数
        strategy_has_max_positions = strategy and hasattr(strategy, 'max_positions')
        strategy_has_max_stocks_per_day = strategy and hasattr(strategy, 'max_stocks_per_day')
        strategy_has_position_ratio = strategy and hasattr(strategy, 'position_ratio')
        
        if strategy_has_max_positions:
            max_positions = strategy.max_positions
        else:
            max_positions = None  # None 表示不限制持仓数量
        
        # 【关键修复】支持 max_stocks_per_day：限制每天买入的股票数量（不是总持仓）
        if strategy_has_max_stocks_per_day:
            max_stocks_per_day = strategy.max_stocks_per_day
        else:
            max_stocks_per_day = None  # None 表示不限制每天买入数量
        
        if strategy_has_position_ratio:
            position_ratio = strategy.position_ratio
        else:
            position_ratio = None  # None 表示不限制单只股票仓位比例
        
        # 【关键修复】优先使用 max_stocks_per_day（每天买入限制），其次使用 max_positions（总持仓限制）
        if max_stocks_per_day is not None:
            # 策略提供了 max_stocks_per_day，限制每天买入数量
            stocks_to_buy = buy_signals[:max_stocks_per_day]
        elif max_positions is not None:
            # 策略提供了 max_positions，限制持仓数量
            buy_allowance = max_positions - len(new_portfolio)
            stocks_to_buy = buy_signals[:buy_allowance] if buy_allowance > 0 else []
        else:
            # 策略未提供限制参数，买入所有信号
            stocks_to_buy = buy_signals
        
        if stocks_to_buy:
            total_equity = sum(p['shares']*p['entry_price'] for p in portfolio.values()) + cash
            available_cash = cash
            BOARD_LOT = int(os.getenv('BOARD_LOT', self.DEFAULT_BOARD_LOT))
            
            # 计算每只股票的目标投资金额
            if position_ratio is not None:
                # 策略提供了 position_ratio，使用固定比例（基于总资产）
                target_per_stock = total_equity * position_ratio
            else:
                # 策略未提供 position_ratio，平均分配初始可用资金
                # 在循环开始前计算，确保每只股票分配金额固定
                target_per_stock = cash / len(stocks_to_buy) if stocks_to_buy else 0

            for stock_code in stocks_to_buy:
                if stock_code not in new_portfolio and stock_code in price_map:
                    try:
                        current_price = resolve_price(stock_code, 'buy')
                        if current_price is None or current_price <= 0 or np.isnan(current_price):
                            continue
                        
                        investment = min(target_per_stock, available_cash)
                        if investment <= 0 or np.isnan(investment): continue
                        
                        min_comm = float(os.getenv('MIN_COMMISSION', self.DEFAULT_MIN_COMMISSION))
                        est_rate = max(self.commission_rate, min_comm / (investment + 1))
                        if np.isnan(est_rate):
                            continue
                        
                        price_with_rate = current_price * (1 + est_rate)
                        if price_with_rate <= 0 or np.isnan(price_with_rate):
                            continue
                        
                        max_shares = int(investment / price_with_rate)
                        if max_shares <= 0: continue
                        shares = (max_shares // BOARD_LOT) * BOARD_LOT
                        
                        if shares < BOARD_LOT: continue
                        
                        comm = max(shares * current_price * self.commission_rate, min_comm)
                        cost = shares * current_price + comm
                        
                        if cost > available_cash: continue
                        
                        available_cash -= cost
                        position_id = f"{stock_code}_{date}"
                        
                        # 【核心修复 P1】记录买入时的 adj_factor 和收盘价，用于后续除权除息处理
                        entry_adj_factor = None
                        entry_close = None
                        if stock_pool_raw is not None and not stock_pool_raw.empty:
                            stock_data = stock_pool_raw[stock_pool_raw['stock_code'] == stock_code]
                            if not stock_data.empty:
                                if 'adj_factor' in stock_data.columns:
                                    entry_adj_factor = stock_data.iloc[0]['adj_factor']
                                if 'close' in stock_data.columns:
                                    entry_close = stock_data.iloc[0]['close']
                        
                        new_portfolio[stock_code] = {
                            "shares": shares,
                            "entry_price": current_price,
                            "entry_date": date,
                            "position_id": position_id,
                            "entry_adj_factor": entry_adj_factor,  # 记录买入时的复权因子
                            "entry_close": entry_close,  # 记录买入时的收盘价（用于区分送股和分红）
                        }
                        
                        daily_trades.append({
                            "date": date,
                            "symbol": stock_code,
                            "symbol_code": stock_code,
                            "action": "buy",
                            "price": current_price,
                            "quantity": shares,
                            "commission": comm,
                            "position_id": position_id,
                            "entry_date": date,
                        })
                    except Exception as e:
                        logger.error(f"买入失败 {stock_code}: {e}")
            
            cash = available_cash

        return new_portfolio, cash, daily_trades

    def generate_report(self, results_df):
        pass
        
    def _calculate_metrics_from_df(self, results_df: pd.DataFrame, trades_log: List[Dict]) -> Dict:
        """ 用于流式回测的最终指标计算 """
        if results_df.empty: return {}
        
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
        win_trades = 0
        total_profit = 0
        total_loss = 0
        sell_trades = [t for t in trades_log if t['action'] == 'sell']
        
        for t in sell_trades:
            pnl = t.get('profit_loss', 0)
            if pnl > 0:
                win_trades += 1
                total_profit += pnl
            else:
                total_loss += abs(pnl)
                
        trades_count = len(trades_log)
        win_rate = (win_trades / len(sell_trades)) * 100 if sell_trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        # 将可能是 ndarray/cupy 数组的数值安全转换为 Python float，避免 round(ndarray) 报错
        def _to_scalar(x):
            try:
                if isinstance(x, (int, float)):
                    return float(x)
                arr = np.asarray(x)
                # 0 维标量数组
                if getattr(arr, "shape", None) == ():
                    return float(arr)
                # 高维数组，退化为平均值
                return float(arr.mean())
            except Exception:
                return 0.0

        total_return_v = _to_scalar(total_return)
        annualized_return_v = _to_scalar(annualized_return)
        max_drawdown_v = _to_scalar(max_drawdown)
        sharpe_ratio_v = _to_scalar(sharpe_ratio)
        sortino_v = _to_scalar(sortino)
        volatility_v = _to_scalar(volatility)
        win_rate_v = _to_scalar(win_rate)
        profit_factor_v = _to_scalar(profit_factor)

        # Calmar 比率 = 年化收益率 / |最大回撤|
        calmar_ratio_v = 0.0
        if abs(max_drawdown_v) > 1e-8:
            calmar_ratio_v = annualized_return_v / abs(max_drawdown_v)

        # 【新增】添加可交易性过滤统计
        filter_stats = {
            "limitUpBlocked": self._filter_stats['limit_up_blocked'],
            "limitDownBlocked": self._filter_stats['limit_down_blocked'],
            "suspendedBlocked": self._filter_stats['suspended_blocked'],
            "totalBlocked": self._filter_stats['total_blocked']
        }
        
        return {
            "totalReturn": round(total_return_v, 2),
            "annualizedReturn": round(annualized_return_v, 2),
            "maxDrawdown": round(abs(max_drawdown_v), 2),
            "sharpeRatio": round(sharpe_ratio_v, 2),
            "calmarRatio": round(calmar_ratio_v, 3),
            "sortinoRatio": round(sortino_v, 2),
            "volatility": round(volatility_v, 2),
            "winRate": round(win_rate_v, 1),
            "profitFactor": round(profit_factor_v, 2),
            "tradesCount": trades_count,
            "avgTradeReturn": 0, # 简化
            "maxWinningStreak": 0,
            "maxLosingStreak": 0,
            "filterStats": filter_stats  # 【新增】可交易性过滤统计
        }

        
    async def run_backtest_realtime(
        self, start_date: str, end_date: str, strategy
    ) -> AsyncGenerator[Dict[str, Any], None]:
        pass