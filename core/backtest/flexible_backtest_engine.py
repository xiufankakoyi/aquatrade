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
from tqdm import tqdm
import time


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
        'jit_compiled': False
    }
    
    # 1. 检测数据后端
    if hasattr(data_query, '_use_lancedb') and data_query._use_lancedb:
        if hasattr(data_query, 'lance_manager'):
            arch['data_backend'] = 'LanceDB'
        else:
            arch['data_backend'] = 'LanceDB (未初始化)'
    elif hasattr(data_query, '_use_duckdb') and data_query._use_duckdb:
        arch['data_backend'] = 'DuckDB'
    else:
        arch['data_backend'] = 'SQLite/其他'
    
    # 2. 检测数据格式
    if stock_pool is not None:
        if isinstance(stock_pool, pd.DataFrame):
            arch['data_format'] = 'Pandas DataFrame'
        else:
            try:
                import polars as pl
                if isinstance(stock_pool, pl.DataFrame):
                    arch['data_format'] = 'Polars DataFrame'
                elif isinstance(stock_pool, pl.LazyFrame):
                    arch['data_format'] = 'Polars LazyFrame'
                else:
                    import numpy as np
                    if isinstance(stock_pool, np.ndarray):
                        arch['data_format'] = 'NumPy Array'
                    else:
                        arch['data_format'] = f'{type(stock_pool).__name__}'
            except ImportError:
                import numpy as np
                if isinstance(stock_pool, np.ndarray):
                    arch['data_format'] = 'NumPy Array'
                else:
                    arch['data_format'] = f'{type(stock_pool).__name__}'
    
    # 3. 检测计算后端
    try:
        import numba
        arch['compute_backend'] = 'Numba (可用)'
    except ImportError:
        arch['compute_backend'] = 'Python (无Numba)'
    
    # 4. 检测是否使用预加载
    if hasattr(data_query, '_preloaded_data') and data_query._preloaded_data is not None:
        arch['preloaded'] = True
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
        
        # 流式循环
        for idx, current_time in enumerate(tqdm(time_series, desc=f"回测进度 ({self.time_granularity})"), 1):
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
                stock_pool = self._get_stock_pool_at_time(current_time)
                perf_breakdown['data_load'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 检测架构（仅在第一天或每10天检测一次）
                if idx == 1 or idx % 10 == 0:
                    arch_info = _detect_architecture(self.data_query, stock_pool)
                
                if stock_pool is None or stock_pool.empty:
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
                signals = strategy.generate_signals(
                    current_date=current_time.strftime("%Y-%m-%d"),
                    stock_pool_today=stock_pool,
                    data_query=self.data_query
                )
                perf_breakdown['signal_generation'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 执行交易
                t0 = time.perf_counter()
                portfolio, cash, trades = self._execute_trades(
                    current_time,
                    stock_pool,
                    signals,
                    portfolio,
                    cash
                )
                perf_breakdown['execute_trades'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 记录交易
                t0 = time.perf_counter()
                all_trades_log.extend(trades)
                perf_breakdown['log_trades'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 计算账户价值
                t0 = time.perf_counter()
                total_value = self._calculate_portfolio_value(
                    current_time,
                    stock_pool,
                    portfolio,
                    cash
                )
                perf_breakdown['calc_value'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 产出每日更新
                t0 = time.perf_counter()
                if self.time_granularity == 'daily' or idx % self._get_update_frequency() == 0:
                    yield {
                        "type": "daily_equity",
                        "data": {
                            "date": current_time.strftime("%Y-%m-%d"),
                            "equity": total_value,
                            "cash": cash,
                            "positions": len(portfolio),
                            "trades": len(trades)
                        }
                    }
                perf_breakdown['yield_data'] = (time.perf_counter() - t0) * 1000  # ms
                
                # 计算总耗时
                perf_breakdown['total'] = (time.perf_counter() - day_start) * 1000  # ms
                
                # 输出性能分析（仅在前10天或总耗时>100ms时输出）
                if idx <= 10 or perf_breakdown['total'] > 100:
                    # 构建架构信息字符串
                    arch_str = ""
                    if arch_info:
                        arch_str = f" | 架构: {arch_info.get('data_backend', '?')}/{arch_info.get('data_format', '?')}"
                        if arch_info.get('preloaded'):
                            arch_str += " [预加载]"
                        else:
                            arch_str += " [未预加载]"
                    
                    logger.warning(f"[PERF][Day {idx}] {current_time.strftime('%Y-%m-%d')}: "
                          f"总耗时={perf_breakdown['total']:.1f}ms | "
                          f"数据加载={perf_breakdown['data_load']:.1f}ms | "
                          f"信号生成={perf_breakdown['signal_generation']:.1f}ms | "
                          f"交易执行={perf_breakdown['execute_trades']:.1f}ms | "
                          f"价值计算={perf_breakdown['calc_value']:.1f}ms | "
                          f"数据传输={perf_breakdown['yield_data']:.1f}ms{arch_str}")
                    
                    # 如果是第一天，输出详细的架构信息
                    if idx == 1 and arch_info:
                        logger.warning(f"[ARCH] ========== 回测引擎架构检测 ==========")
                        logger.warning(f"[ARCH] 引擎: {arch_info.get('engine', '?')}")
                        logger.warning(f"[ARCH] 数据后端: {arch_info.get('data_backend', '?')}")
                        logger.warning(f"[ARCH] 数据格式: {arch_info.get('data_format', '?')}")
                        logger.warning(f"[ARCH] 计算后端: {arch_info.get('compute_backend', '?')}")
                        logger.warning(f"[ARCH] 数据预加载: {'是' if arch_info.get('preloaded') else '否'}")
                        if not arch_info.get('preloaded'):
                            logger.warning(f"[ARCH] ⚠️  警告: 未使用数据预加载，性能可能较差！")
                        if arch_info.get('data_backend') != 'LanceDB':
                            logger.warning(f"[ARCH] ⚠️  警告: 未使用LanceDB后端，性能可能较差！")
                        if arch_info.get('data_format') == 'Pandas DataFrame':
                            logger.warning(f"[ARCH] ⚠️  警告: 使用Pandas DataFrame，建议使用Polars或NumPy！")
                        logger.warning(f"[ARCH] ======================================")
                
            except Exception as e:
                yield {
                    "type": "error",
                    "data": {"message": f"回测过程中出错: {str(e)}"}
                }
                import traceback
                traceback.print_exc()
        
        # 产出最终结果
        yield {
            "type": "backtest_complete",
            "data": {
                "finalEquity": total_value,
                "totalReturn": (total_value - self.initial_capital) / self.initial_capital,
                "totalTrades": len(all_trades_log),
                "trades": all_trades_log[-100:]  # 最后100笔交易
            }
        }
    
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
    
    def _get_stock_pool_at_time(self, current_time: pd.Timestamp) -> Optional[pd.DataFrame]:
        """
        获取指定时间点的股票池
        
        参数：
            current_time: 当前时间
        
        返回：
            DataFrame or None
        """
        if self.time_granularity == 'daily':
            # 日线：使用现有方法
            return self.data_query.get_stock_pool(
                current_time.strftime("%Y-%m-%d")
            )
        
        elif self.time_granularity == 'minute':
            # 分钟线：需要查询分钟数据表
            # 这里简化处理，实际应该查询分钟数据
            # 暂时回退到日线数据
            return self.data_query.get_stock_pool(
                current_time.strftime("%Y-%m-%d")
            )
        
        else:
            return None
    
    def _execute_trades(
        self,
        current_time: pd.Timestamp,
        stock_pool: pd.DataFrame,
        signals: Dict[str, str],
        portfolio: Dict[str, int],
        cash: float
    ) -> tuple:
        """
        执行交易
        
        返回：
            (portfolio, cash, trades)
        """
        trades = []
        new_portfolio = portfolio.copy()
        new_cash = cash
        
        for code, signal in signals.items():
            if code not in stock_pool.index:
                continue
            
            stock_data = stock_pool.loc[code]
            price = float(stock_data.get('close', 0))
            
            if price <= 0:
                continue
            
            current_position = new_portfolio.get(code, 0)
            
            if signal == 'buy' and current_position == 0:
                # 买入
                # 简化：使用固定仓位大小
                shares = int(new_cash * 0.1 / price)  # 使用10%资金
                
                if shares > 0:
                    cost = shares * price
                    commission = max(cost * self.commission_rate, self.min_commission)
                    total_cost = cost + commission
                    
                    if total_cost <= new_cash:
                        new_portfolio[code] = shares
                        new_cash -= total_cost
                        
                        trades.append({
                            "date": current_time.strftime("%Y-%m-%d"),
                            "code": code,
                            "action": "buy",
                            "shares": shares,
                            "price": price,
                            "cost": total_cost
                        })
            
            elif signal == 'sell' and current_position > 0:
                # 卖出
                revenue = current_position * price
                commission = max(revenue * self.commission_rate, self.min_commission)
                net_revenue = revenue - commission
                
                new_cash += net_revenue
                del new_portfolio[code]
                
                trades.append({
                    "date": current_time.strftime("%Y-%m-%d"),
                    "code": code,
                    "action": "sell",
                    "shares": current_position,
                    "price": price,
                    "revenue": net_revenue
                })
        
        return new_portfolio, new_cash, trades
    
    def _calculate_portfolio_value(
        self,
        current_time: pd.Timestamp,
        stock_pool: pd.DataFrame,
        portfolio: Dict[str, int],
        cash: float
    ) -> float:
        """计算账户总价值（向量化优化版本）"""
        if not portfolio:
            return cash
        
        # 将 stock_pool 转换为价格映射（O(1) 查找）
        # 如果 stock_pool 使用 stock_code 作为索引，直接使用
        if stock_pool is not None and not stock_pool.empty:
            if 'stock_code' in stock_pool.columns:
                # 如果 stock_pool 有 stock_code 列，创建索引映射
                price_map = stock_pool.drop_duplicates(subset='stock_code').set_index('stock_code')['close']
            else:
                # 如果已经是索引，直接使用
                price_map = stock_pool['close'] if 'close' in stock_pool.columns else pd.Series(dtype=float)
        else:
            price_map = pd.Series(dtype=float)
        
        # 向量化计算：一次性获取所有持仓的价格和股数
        portfolio_codes = list(portfolio.keys())
        shares_series = pd.Series(portfolio)
        
        # 从 price_map 中获取价格（O(1) 查找）
        prices = price_map.reindex(portfolio_codes)
        
        # 向量化计算总市值（只计算有价格的持仓）
        mask = prices.notna()
        portfolio_value = (shares_series[mask] * prices[mask]).sum()
        
        return cash + portfolio_value
    
    def _get_update_frequency(self) -> int:
        """获取更新频率（用于非日线粒度）"""
        if self.time_granularity == 'daily':
            return 1
        elif self.time_granularity == 'minute':
            return 60  # 每60分钟更新一次
        else:
            return 1

