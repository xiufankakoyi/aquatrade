"""
统一回测引擎 - 向量化优先，配置化驱动

架构说明：
1. DataLayer: 数据加载与缓存 (Polars/Pandas/NumPy)
2. ComputeLayer: 指标计算 (向量化/Numba/GPU)
3. SignalLayer: 信号生成 (配置化规则引擎或策略类)
4. ExecutionLayer: 交易执行 (T+1/涨跌停/停牌/分红)
5. ReportLayer: 结果输出 (权益曲线/交易记录/风险指标)

设计理念：
- 单一引擎：消除 flexible 和 optimized 的割裂感
- 向量化优先：所有计算尽可能使用 NumPy/Pandas/Polars 向量化
- 配置化驱动：策略可以是 Python 类或 YAML/JSON 配置
- 性能一致：无论策略形式如何，都享受相同的性能优化
"""

import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, Any, Generator, Tuple, List, Optional, Union, Callable
from threading import Event
from dataclasses import dataclass, field
from enum import Enum
import time
import json
from pathlib import Path
from functools import lru_cache
import hashlib

# 可选依赖导入
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import numba
    from numba import jit, njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    njit = lambda *args, **kwargs: lambda f: f

from config.logger import get_logger
from config.config import Config

logger = get_logger(__name__)


# =============================================================================
# [性能优化] Numba 加速函数
# =============================================================================
if NUMBA_AVAILABLE:
    @njit(cache=True, fastmath=True)
    def _calculate_drawdown_numba(equity_values: np.ndarray) -> float:
        """
        Numba 加速的最大回撤计算
        
        Args:
            equity_values: 权益曲线数组
        
        Returns:
            float: 最大回撤百分比（负数）
        """
        n = len(equity_values)
        if n == 0:
            return 0.0
        
        peak = equity_values[0]
        max_dd = 0.0
        
        for i in range(n):
            if equity_values[i] > peak:
                peak = equity_values[i]
            if peak > 0:
                dd = (equity_values[i] - peak) / peak * 100
                if dd < max_dd:
                    max_dd = dd
        
        return max_dd
    
    @njit(cache=True, fastmath=True)
    def _calculate_sharpe_numba(returns: np.ndarray, annual_factor: float = 252.0) -> float:
        """
        Numba 加速的夏普比率计算
        
        Args:
            returns: 日收益率数组
            annual_factor: 年化因子
        
        Returns:
            float: 夏普比率
        """
        n = len(returns)
        if n < 2:
            return 0.0
        
        mean_ret = 0.0
        for i in range(n):
            mean_ret += returns[i]
        mean_ret /= n
        
        var = 0.0
        for i in range(n):
            diff = returns[i] - mean_ret
            var += diff * diff
        var /= (n - 1)
        
        std_ret = np.sqrt(var)
        if std_ret <= 0:
            return 0.0
        
        return (mean_ret / std_ret) * np.sqrt(annual_factor)
    
    @njit(cache=True, fastmath=True)
    def _calculate_sortino_numba(returns: np.ndarray, annual_factor: float = 252.0) -> float:
        """
        Numba 加速的索提诺比率计算
        
        Args:
            returns: 日收益率数组
            annual_factor: 年化因子
        
        Returns:
            float: 索提诺比率
        """
        n = len(returns)
        if n < 2:
            return 0.0
        
        mean_ret = 0.0
        for i in range(n):
            mean_ret += returns[i]
        mean_ret /= n
        
        # 计算下行波动率
        downside_count = 0
        downside_var = 0.0
        for i in range(n):
            if returns[i] < 0:
                diff = returns[i] - mean_ret
                downside_var += diff * diff
                downside_count += 1
        
        if downside_count < 1:
            return 0.0
        
        downside_var /= downside_count
        downside_std = np.sqrt(downside_var)
        
        if downside_std <= 0:
            return 0.0
        
        return (mean_ret / downside_std) * np.sqrt(annual_factor)
    
    @njit(cache=True, fastmath=True)
    def _calculate_streaks_numba(profit_signs: np.ndarray) -> Tuple[int, int]:
        """
        Numba 加速的连胜/连亏计算
        
        Args:
            profit_signs: 盈亏符号数组 (1=盈利, -1=亏损, 0=持平)
        
        Returns:
            Tuple[int, int]: (最大连胜次数, 最大连亏次数)
        """
        n = len(profit_signs)
        if n == 0:
            return 0, 0
        
        max_win = 0
        max_loss = 0
        cur_win = 0
        cur_loss = 0
        
        for i in range(n):
            if profit_signs[i] > 0:
                cur_win += 1
                cur_loss = 0
                if cur_win > max_win:
                    max_win = cur_win
            elif profit_signs[i] < 0:
                cur_loss += 1
                cur_win = 0
                if cur_loss > max_loss:
                    max_loss = cur_loss
        
        return max_win, max_loss

else:
    def _calculate_drawdown_numba(equity_values: np.ndarray) -> float:
        """回退实现：最大回撤计算"""
        if len(equity_values) == 0:
            return 0.0
        peak = np.maximum.accumulate(equity_values)
        with np.errstate(divide='ignore', invalid='ignore'):
            drawdowns = np.where(peak > 0, (equity_values - peak) / peak * 100, 0)
        return float(np.min(drawdowns))
    
    def _calculate_sharpe_numba(returns: np.ndarray, annual_factor: float = 252.0) -> float:
        """回退实现：夏普比率计算"""
        if len(returns) < 2:
            return 0.0
        std_ret = np.std(returns)
        if std_ret <= 0:
            return 0.0
        return float((np.mean(returns) / std_ret) * np.sqrt(annual_factor))
    
    def _calculate_sortino_numba(returns: np.ndarray, annual_factor: float = 252.0) -> float:
        """回退实现：索提诺比率计算"""
        if len(returns) < 2:
            return 0.0
        downside_returns = returns[returns < 0]
        if len(downside_returns) < 1:
            return 0.0
        downside_std = np.std(downside_returns)
        if downside_std <= 0:
            return 0.0
        return float((np.mean(returns) / downside_std) * np.sqrt(annual_factor))
    
    def _calculate_streaks_numba(profit_signs: np.ndarray) -> Tuple[int, int]:
        """回退实现：连胜/连亏计算"""
        max_win = max_loss = cur_win = cur_loss = 0
        for sign in profit_signs:
            if sign > 0:
                cur_win += 1
                cur_loss = 0
                max_win = max(max_win, cur_win)
            elif sign < 0:
                cur_loss += 1
                cur_win = 0
                max_loss = max(max_loss, cur_loss)
        return max_win, max_loss


class TimeGranularity(Enum):
    """时间粒度枚举"""
    DAILY = "daily"
    MINUTE = "minute"
    TICK = "tick"


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    sell_tax: float = 0.001  # 印花税
    time_granularity: TimeGranularity = TimeGranularity.DAILY

    # 风控参数
    max_positions: Optional[int] = None
    position_ratio: float = 0.1
    max_stocks_per_day: Optional[int] = None  # 单日最大买入股票数
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None  # 止盈比例
    max_holding_days: Optional[int] = None

    # 执行参数
    warmup_days: int = 30  # 预热期天数
    execution_price: str = "open"  # 执行价格: open/close

    # ===== 回测真实性参数 =====
    # 滑点：买入按 (1+slippage_rate) 加价，卖出按 (1-slippage_rate) 减价
    slippage_rate: float = 0.001  # 0.1%，A股市场常见水平
    # 是否启用 ST 股票过滤（默认 True，避免踩雷）
    exclude_st: bool = True
    # 成交量约束：单笔买入股数 <= 当日成交量 × volume_cap_ratio（剩余仓位会被拒绝）
    volume_cap_ratio: float = 0.05  # 单笔不超过日成交量 5%
    # 最小可买入金额（资金不足阈值）
    min_trade_amount: float = 1000.0


@dataclass
class RejectedOrderStat:
    """不可成交订单统计"""
    suspended: int = 0       # 停牌
    limit_up: int = 0        # 涨停未开板
    limit_down: int = 0      # 跌停
    st: int = 0              # ST 股
    volume: int = 0          # 成交量不足
    insufficient_cash: int = 0  # 现金不足
    invalid_price: int = 0   # 价格无效
    other: int = 0

    def total(self) -> int:
        return (
            self.suspended + self.limit_up + self.limit_down
            + self.st + self.volume + self.insufficient_cash
            + self.invalid_price + self.other
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "suspended": self.suspended,
            "limitUp": self.limit_up,
            "limitDown": self.limit_down,
            "st": self.st,
            "volume": self.volume,
            "insufficientCash": self.insufficient_cash,
            "invalidPrice": self.invalid_price,
            "other": self.other,
            "total": self.total(),
        }


@dataclass
class TradeRecord:
    """
    交易记录
    
    字段说明：
    - date: 交易日期
    - code: 股票代码（6位数字）
    - action: 交易方向 (buy/sell)
    - shares: 成交股数
    - price: 成交价格（前复权）
    - amount: 成交金额
    - commission: 佣金
    - tax: 印花税（仅卖出）
    - profit_loss: 盈亏金额（仅卖出）
    - roi: 收益率（仅卖出）
    - entry_price: 开仓价格
    - entry_date: 开仓日期
    - exit_price: 平仓价格（仅卖出）
    - exit_date: 平仓日期（仅卖出）
    - holding_days: 持仓天数
    - position_id: 持仓ID（用于买卖配对）
    - indicators: 策略指标快照
    """
    date: str
    code: str
    action: str  # buy/sell
    shares: int
    price: float
    amount: float
    commission: float
    tax: float = 0.0
    profit_loss: float = 0.0
    roi: float = 0.0
    entry_price: float = 0.0
    entry_date: str = ""
    exit_price: float = 0.0
    exit_date: str = ""
    holding_days: int = 0
    position_id: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """回测结果"""
    final_equity: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    volatility: float
    win_rate: float
    profit_factor: float
    trade_count: int
    avg_trade_return: float
    max_winning_streak: int
    max_losing_streak: int
    calmar_ratio: float
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[TradeRecord] = field(default_factory=list)
    # 真实性统计
    rejected_orders: Dict[str, int] = field(default_factory=dict)
    slippage_cost: float = 0.0
    filter_stats: Dict[str, Any] = field(default_factory=dict)


def _make_json_serializable(obj: Any, max_depth: int = 10, _current_depth: int = 0) -> Any:
    """递归将对象转换为 JSON 可序列化的类型"""
    if _current_depth > max_depth:
        return None
    
    if obj is None or isinstance(obj, bool):
        return obj
    elif isinstance(obj, (int, float)):
        import math
        if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
            return None
        elif hasattr(obj, 'item'):
            try:
                val = obj.item()
                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                    return None
            except:
                pass
        return obj
    elif isinstance(obj, str):
        return obj
    
    if hasattr(obj, 'tolist'):
        try:
            return obj.tolist()
        except (AttributeError, ValueError):
            pass
    elif isinstance(obj, np.generic):
        try:
            return float(obj) if isinstance(obj, (np.floating, np.integer)) else str(obj)
        except (ValueError, TypeError):
            return None
    
    if isinstance(obj, pd.DataFrame):
        return _make_json_serializable(obj.to_dict('records'), max_depth, _current_depth)
    if isinstance(obj, pd.Series):
        return _make_json_serializable(obj.to_dict(), max_depth, _current_depth)
    
    if isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        try:
            return obj.isoformat()
        except (AttributeError, ValueError):
            return str(obj)
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    if isinstance(obj, (list, tuple)):
        result = []
        for item in obj:
            try:
                result.append(_make_json_serializable(item, max_depth, _current_depth + 1))
            except Exception:
                result.append(str(item))
        return result if isinstance(obj, list) else tuple(result)
    
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            try:
                key = _make_json_serializable(k, max_depth, _current_depth + 1) if not isinstance(k, (str, int, float, bool)) else k
                if key is not None:
                    result[key] = _make_json_serializable(v, max_depth, _current_depth + 1)
            except Exception:
                pass
        return result
    
    if isinstance(obj, (set, frozenset)):
        try:
            sorted_items = sorted(_make_json_serializable(list(obj), max_depth, _current_depth + 1))
            return sorted_items
        except (TypeError, ValueError):
            return list(obj)
    
    if hasattr(obj, '__dict__'):
        try:
            result = {}
            for k, v in obj.__dict__.items():
                if k.startswith('_'):
                    continue
                try:
                    result[k] = _make_json_serializable(v, max_depth, _current_depth + 1)
                except Exception:
                    pass
            return result
        except Exception:
            pass
    
    try:
        return str(obj)
    except Exception:
        return None


class UnifiedBacktestEngine:
    """
    统一回测引擎
    
    核心特性：
    1. 向量化优先：使用 NumPy/Pandas/Polars 进行向量化计算
    2. 配置化驱动：支持 YAML/JSON 配置的策略
    3. 多粒度支持：日线、分钟线、Tick级别
    4. 统一接口：无论策略形式如何，使用相同的 API
    
    使用示例：
        # 方式1: 使用策略类
        engine = UnifiedBacktestEngine(data_query, config)
        result = engine.run_backtest(start_date, end_date, strategy_instance)
        
        # 方式2: 使用配置化策略
        engine = UnifiedBacktestEngine(data_query, config)
        result = engine.run_backtest(start_date, end_date, strategy_config)
    """
    
    def __init__(
        self,
        data_query,
        config: Optional[BacktestConfig] = None
    ):
        """
        初始化统一回测引擎
        
        参数：
            data_query: 数据查询对象
            config: 回测配置，使用默认配置如果为 None
        """
        self.data_query = data_query
        self.config = config or BacktestConfig()
        
        # 缓存
        self._stock_pool_cache: Dict[str, pd.DataFrame] = {}
        self._cache_order: List[str] = []
        self._cache_max_size = 1000
        
        # 权益曲线历史
        self._equity_history: List[Tuple[str, float]] = []
        
        # 向量化模式状态
        self._vectorized_mode = False
        self._signal_matrix: Optional[np.ndarray] = None
        self._stock_codes_list: Optional[List[str]] = None
        self._date_to_idx: Optional[Dict[str, int]] = None
        
        # 因子矩阵（三维数组）
        self._factor_matrix: Optional[Any] = None  # FactorMatrix 对象

        # 回测真实性统计（每次 run_backtest 时重置）
        self._rejected_stats = RejectedOrderStat()
        self._slippage_cost_total: float = 0.0

        logger.info(
            f"✅ UnifiedBacktestEngine 初始化完成 "
            f"(资金: {self.config.initial_capital:,.0f}, "
            f"粒度: {self.config.time_granularity.value}, "
            f"滑点: {self.config.slippage_rate*100:.2f}%, "
            f"排除ST: {self.config.exclude_st})"
        )

    def reset_realism_stats(self) -> None:
        """重置回测真实性统计计数器（每次 run_backtest 入口自动调用）"""
        self._rejected_stats = RejectedOrderStat()
        self._slippage_cost_total = 0.0

    def get_rejected_stats(self) -> RejectedOrderStat:
        return self._rejected_stats

    def get_slippage_cost(self) -> float:
        return self._slippage_cost_total
    
    @property
    def initial_capital(self) -> float:
        """获取初始资金（便捷属性）"""
        return self.config.initial_capital
    
    @property
    def commission_rate(self) -> float:
        """获取手续费率（便捷属性）"""
        return self.config.commission_rate
    
    def run_backtest_streaming(
        self,
        start_date: Union[str, pd.Timestamp, datetime],
        end_date: Union[str, pd.Timestamp, datetime],
        strategy: Any,
        stop_event: Optional[Event] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式回测（run_backtest 的别名，保持向后兼容）
        
        参数：
            start_date: 开始日期
            end_date: 结束日期
            strategy: 策略实例或配置
            stop_event: 停止事件
            
        返回：
            Generator，产出回测事件
        """
        yield from self.run_backtest(start_date, end_date, strategy, stop_event)
    
    def run_backtest(
        self,
        start_date: Union[str, pd.Timestamp, datetime],
        end_date: Union[str, pd.Timestamp, datetime],
        strategy: Any,
        stop_event: Optional[Event] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        运行回测（流式生成器）
        
        参数：
            start_date: 开始日期
            end_date: 结束日期
            strategy: 策略实例或配置
            stop_event: 停止事件
            
        返回：
            Generator，产出回测事件
        """
        # 标准化日期
        start_ts = self._normalize_datetime(start_date)
        end_ts = self._normalize_datetime(end_date)

        if start_ts >= end_ts:
            yield {"type": "error", "data": {"message": "开始日期必须早于结束日期"}}
            return

        # 重置回测真实性统计
        self.reset_realism_stats()

        # 获取时间序列
        time_series = self._get_time_series(start_ts, end_ts)
        if not time_series:
            yield {"type": "error", "data": {"message": "未找到有效的时间序列"}}
            return

        # 清除历史数据
        self._equity_history = []

        # [性能优化] 清除矩阵缓存，确保新回测从头开始
        from core.strategies.vectorized_base import clear_matrix_cache
        clear_matrix_cache()
        
        # 初始化账户
        portfolio: Dict[str, int] = {}
        cash = self.config.initial_capital
        all_trades: List[TradeRecord] = []
        position_info: Dict[str, Dict[str, Any]] = {}
        prev_day_data: Dict[str, Dict[str, Any]] = {}
        
        # 产出开始信号
        yield {
            "type": "backtest_start",
            "data": {
                "initialCapital": self.config.initial_capital,
                "timeGranularity": self.config.time_granularity.value,
                "startDate": start_ts.strftime("%Y-%m-%d"),
                "endDate": end_ts.strftime("%Y-%m-%d")
            }
        }
        
        # 预加载数据
        t_preload_start = time.perf_counter()
        preloaded_data = self._preload_data(start_ts, end_ts, strategy)
        preload_time = (time.perf_counter() - t_preload_start)*1000
        print(f"[PERF-TRACE] _preload_data 耗时: {preload_time:.1f}ms")
        logger.info(f"[PERF] _preload_data 耗时: {preload_time:.1f}ms")
        
        # [声明式因子系统] 预加载策略声明的因子
        t_factors_start = time.perf_counter()
        self._preload_factors(strategy, preloaded_data)
        factors_time = (time.perf_counter() - t_factors_start)*1000
        print(f"[PERF-TRACE] _preload_factors 耗时: {factors_time:.1f}ms")
        logger.info(f"[PERF] _preload_factors 耗时: {factors_time:.1f}ms")
        
        # 主循环
        perf_snapshots = []
        total_steps = len(time_series)
        
        for idx, current_time in enumerate(time_series, 1):
            if stop_event and stop_event.is_set():
                yield {"type": "backtest_cancelled", "data": {"message": "回测已取消"}}
                return
            
            day_start = time.perf_counter()
            perf_breakdown = {}
            
            logger.debug(f"[Day {idx}] 开始加载数据: {current_time}")
            
            try:
                # 1. 加载当日数据
                t0 = time.perf_counter()
                stock_pool, use_pl, data_dict = self._load_day_data(current_time)
                perf_breakdown['data_load'] = (time.perf_counter() - t0) * 1000
                
                logger.debug(f"[Day {idx}] 数据加载完成: {perf_breakdown['data_load']:.1f}ms")
                
                if stock_pool is None:
                    continue
                
                if isinstance(stock_pool, np.ndarray):
                    if stock_pool.size == 0:
                        continue
                elif use_pl and hasattr(stock_pool, 'is_empty'):
                    if stock_pool.is_empty():
                        continue
                elif hasattr(stock_pool, 'empty') and stock_pool.empty:
                    continue
                
                # 2. 设置策略上下文
                t0 = time.perf_counter()
                self._set_strategy_context(strategy, current_time, portfolio, cash)
                perf_breakdown['set_context'] = (time.perf_counter() - t0) * 1000
                
                # 3. 生成信号
                t0 = time.perf_counter()
                signals = self._generate_signals(
                    strategy, current_time, stock_pool, preloaded_data, idx, time_series
                )
                perf_breakdown['signal_generation'] = (time.perf_counter() - t0) * 1000
                if idx == 1:
                    logger.info(f"[PERF] Day 1 _generate_signals 耗时: {perf_breakdown['signal_generation']:.1f}ms")
                
                logger.debug(f"[Day {idx}] signals count: {len(signals)}")
                
                # 4. 执行交易
                t0 = time.perf_counter()
                portfolio, cash, trades = self._execute_trades(
                    current_time, stock_pool, signals, portfolio, cash, position_info, data_dict
                )
                all_trades.extend(trades)
                perf_breakdown['execute_trades'] = (time.perf_counter() - t0) * 1000
                
                logger.debug(f"[Day {idx}] signals: {len(signals)}, stock_pool: {type(stock_pool)}, data_dict keys: {len(data_dict) if isinstance(data_dict, dict) else 'N/A'}")
                
                logger.debug(f"[Day {idx}] trades count: {len(trades)}")
                
                # 5. 记录并产出交易
                for trade in trades:
                    self._log_trade(trade)
                    yield self._format_trade_event(trade)
                
                # 6. 分红结算
                t0 = time.perf_counter()
                cash, dividends = self._process_dividends(
                    current_time, portfolio, prev_day_data, data_dict, cash
                )
                for div in dividends:
                    yield {"type": "dividend_payout", "data": div}
                perf_breakdown['dividend_settlement'] = (time.perf_counter() - t0) * 1000
                
                # 7. 计算账户价值
                t0 = time.perf_counter()
                portfolio_value = self._calculate_portfolio_value(portfolio, data_dict)
                total_value = cash + portfolio_value
                perf_breakdown['calc_value'] = (time.perf_counter() - t0) * 1000
                
                # 8. 更新前一日数据
                prev_day_data = data_dict
                
                # 9. 记录权益曲线
                if self._should_record_equity(idx):
                    self._equity_history.append((current_time.strftime("%Y-%m-%d"), total_value))
                    yield {
                        "type": "daily_equity_engine",
                        "data": {
                            "date": current_time.strftime("%Y-%m-%d"),
                            "equity": total_value,
                            "strategyReturn": total_value,
                            "cash": cash,
                            "positions": len(portfolio),
                            "trades": len(trades)
                        }
                    }
                
                # 10. 性能记录
                perf_breakdown['total'] = (time.perf_counter() - day_start) * 1000
                perf_snapshots.append({"day": idx, "date": current_time.strftime('%Y-%m-%d'), "metrics": perf_breakdown})
                
                # 11. 进度更新
                if idx % 5 == 0 or idx == total_steps:
                    yield {"type": "progress", "data": {"progress": round((idx / total_steps) * 100, 1)}}
                
                # 12. 慢查询日志
                self._log_performance_if_slow(idx, total_steps, current_time, perf_breakdown)
                
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc()
                logger.error(f"回测过程中出错: {e}\n{tb_str}")
                yield {"type": "error", "data": {"message": f"回测过程中出错: {str(e)}", "traceback": tb_str}}
        
        # 保存性能报告
        self._save_performance_report(perf_snapshots, strategy)
        
        # 计算最终结果
        result = self._calculate_final_result(all_trades, start_ts, end_ts)
        
        # 产出最终指标
        yield {
            "type": "final_metrics",
            "data": {
                "totalReturn": round(result.total_return, 2),
                "annualizedReturn": round(result.annualized_return, 2),
                "maxDrawdown": round(result.max_drawdown, 2),
                "sharpeRatio": round(result.sharpe_ratio, 2),
                "sortinoRatio": round(result.sortino_ratio, 2),
                "volatility": round(result.volatility, 2),
                "winRate": round(result.win_rate, 1),
                "profitFactor": round(result.profit_factor, 2),
                "tradesCount": result.trade_count,
                "avgTradeReturn": round(result.avg_trade_return, 2),
                "maxWinningStreak": result.max_winning_streak,
                "maxLosingStreak": result.max_losing_streak,
                "calmarRatio": round(result.calmar_ratio, 2),
                # 回测真实性统计
                "rejectedOrders": result.rejected_orders,
                "slippageCost": result.slippage_cost,
                "filterStats": result.filter_stats,
            }
        }
        
        # 数据持久化
        self._persist_results(result, all_trades, strategy, start_ts, end_ts)
        
        # 【新增】计算月度收益（格式：{year: number, months: (number | null)[]}）
        monthly_returns = []
        if self._equity_history:
            try:
                df = pd.DataFrame(self._equity_history, columns=['date', 'equity'])
                df['date'] = pd.to_datetime(df['date'])
                df['year'] = df['date'].dt.year
                df['month'] = df['date'].dt.month
                
                for year, year_group in df.groupby('year'):
                    year_data = {
                        'year': int(year),
                        'months': [None] * 12
                    }
                    
                    for month, month_group in year_group.groupby('month'):
                        first_equity = month_group['equity'].iloc[0]
                        last_equity = month_group['equity'].iloc[-1]
                        if first_equity > 0:
                            monthly_return = (last_equity - first_equity) / first_equity * 100
                            year_data['months'][int(month) - 1] = float(round(monthly_return, 2))
                    
                    monthly_returns.append(year_data)
            except Exception as e:
                logger.error(f"[Monthly] 计算月度收益失败: {e}")
        
        # 【新增】获取基准曲线数据
        benchmark_curve = []
        benchmark_return = 0.0
        try:
            if hasattr(self.data_query, 'conn') and self.data_query.conn:
                start_str = start_ts.strftime("%Y-%m-%d")
                end_str = end_ts.strftime("%Y-%m-%d")
                query = f"""
                    SELECT date, close 
                    FROM benchmark_data 
                    WHERE date >= '{start_str}' AND date <= '{end_str}'
                    ORDER BY date
                """
                result_rows = self.data_query.conn.execute(query).fetchall()
                if result_rows:
                    initial_benchmark = result_rows[0][1]
                    final_benchmark = result_rows[-1][1]
                    benchmark_return = round((final_benchmark - initial_benchmark) / initial_benchmark * 100, 2)
                    for row in result_rows:
                        benchmark_curve.append({
                            'date': row[0] if isinstance(row[0], str) else row[0].strftime("%Y-%m-%d"),
                            'equity': round(self.config.initial_capital * row[1] / initial_benchmark, 2)
                        })
        except Exception as e:
            logger.error(f"[Benchmark] 获取基准数据失败: {e}")
        
        # 【新增】计算平均持仓天数
        avg_holding_days = 0.0
        if all_trades:
            sell_trades = [t for t in all_trades if t.action == 'sell']
            if sell_trades:
                total_days = sum(t.holding_days for t in sell_trades if t.holding_days)
                avg_holding_days = total_days / len(sell_trades) if sell_trades else 0.0
        
        # 产出完成事件
        yield {
            "type": "stream_complete",
            "data": {
                "finalEquity": result.final_equity,
                "totalReturn": round(result.total_return, 2),
                "annualizedReturn": round(result.annualized_return, 2),
                "maxDrawdown": round(result.max_drawdown, 2),
                "sharpeRatio": round(result.sharpe_ratio, 2),
                "sortinoRatio": round(result.sortino_ratio, 2),
                "volatility": round(result.volatility, 2),
                "winRate": round(result.win_rate, 1),
                "profitFactor": round(result.profit_factor, 2),
                "totalTrades": result.trade_count,
                "avgTradeReturn": round(result.avg_trade_return, 2),
                "maxWinningStreak": result.max_winning_streak,
                "maxLosingStreak": result.max_losing_streak,
                "calmarRatio": round(result.calmar_ratio, 2),
                "avgHoldingDays": round(avg_holding_days, 1),
                "benchmarkReturn": benchmark_return,
                "equityCurve": result.equity_curve,
                "benchmarkCurve": benchmark_curve,
                "monthlyReturns": monthly_returns,
                "trades": [_trade_to_dict(t) for t in result.trades],
                # 回测真实性统计（同步 final_metrics）
                "rejectedOrders": result.rejected_orders,
                "slippageCost": result.slippage_cost,
                "filterStats": result.filter_stats,
            }
        }
    
    def _normalize_datetime(self, dt: Union[str, pd.Timestamp, datetime]) -> pd.Timestamp:
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
        """根据时间粒度获取时间序列"""
        if self.config.time_granularity == TimeGranularity.DAILY:
            try:
                trading_dates = self.data_query.get_trading_dates(
                    start_ts.strftime("%Y-%m-%d"),
                    end_ts.strftime("%Y-%m-%d")
                )
                return [pd.to_datetime(d) for d in trading_dates]
            except Exception as e:
                logger.error(f"获取交易日失败: {e}")
                return []
        
        elif self.config.time_granularity == TimeGranularity.MINUTE:
            # 简化实现：实际应该生成交易时间
            time_series = []
            current = start_ts.replace(hour=9, minute=30, second=0, microsecond=0)
            while current <= end_ts:
                time_series.append(current)
                current += timedelta(minutes=1)
            return time_series
        
        else:
            raise NotImplementedError(f"Tick级别回测需要实现tick数据查询")
    
    def _preload_data(
        self,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        strategy: Any = None
    ) -> Optional[Dict[str, 'pl.DataFrame']]:
        """
        预加载回测期间的数据（返回 Polars DataFrame 实现零拷贝）
        
        优化：自动推断策略需要的列，减少内存占用和加载时间
        
        优先级：
        1. UnifiedDataManager 内存缓存（零磁盘IO）
        2. 原有的 OptimizedStockDataQuery 预加载
        
        Args:
            start_ts: 开始时间戳
            end_ts: 结束时间戳
            strategy: 策略实例（用于自动推断所需列）
        """
        from core.utils.column_inference import ColumnInference
        
        MINIMAL_FIELDS = [
            'stock_code', 'trade_date',
            'open', 'high', 'low', 'close', 'volume', 'amount',
            'adj_factor', 'prev_close',
            'total_mv', 'limit_up', 'limit_down'
        ]
        
        if strategy is not None:
            try:
                inferred_fields = ColumnInference.get_required_columns(strategy)
                MINIMAL_FIELDS = list(set(MINIMAL_FIELDS) | set(inferred_fields))
                logger.info(f"[Engine] 自动推断所需列: {sorted(inferred_fields)}")
            except Exception as e:
                logger.warning(f"[Engine] 列推断失败，使用默认列: {e}")
        
        load_start_str: str
        load_end_str = end_ts.strftime("%Y-%m-%d")
        
        warmup_days = self.config.warmup_days
        try:
            hist_dates = self.data_query.get_trading_dates(
                (start_ts - timedelta(days=60)).strftime("%Y-%m-%d"),
                (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
            )
            if len(hist_dates) >= warmup_days:
                warmup_start_str = hist_dates[-warmup_days]
            elif hist_dates:
                warmup_start_str = hist_dates[0]
            else:
                warmup_start_str = start_ts.strftime("%Y-%m-%d")
        except Exception:
            warmup_start_str = start_ts.strftime("%Y-%m-%d")
        
        try:
            from data_svc.unified_data_manager import get_unified_manager
            manager = get_unified_manager()
            
            logger.info(f"[Engine] 检查缓存: cache_loaded={manager._cache_loaded}, range={manager._preloaded_date_range}")
            
            try:
                prev_trading_dates = self.data_query.get_trading_dates(
                    (start_ts - timedelta(days=10)).strftime("%Y-%m-%d"),
                    (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
                )
                if prev_trading_dates:
                    actual_start = prev_trading_dates[-1]
                else:
                    actual_start = start_ts.strftime("%Y-%m-%d")
            except Exception:
                actual_start = (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
            
            if manager._cache_loaded and manager._preloaded_date_range:
                cached_start, cached_end = manager._preloaded_date_range
                
                logger.info(f"[Engine] 日期范围: warmup_start={warmup_start_str}, actual_start={actual_start}, load_end={load_end_str}, cached=({cached_start}, {cached_end})")
                
                if warmup_start_str >= cached_start and load_end_str <= cached_end:
                    logger.info(f"[Engine] 使用 UnifiedDataManager 内存缓存: {warmup_start_str} ~ {load_end_str}")
                    
                    preloaded_data = manager.get_preloaded_data(warmup_start_str, load_end_str)
                    stock_daily = preloaded_data.get('daily')
                    
                    logger.info(f"[Engine] daily: {len(stock_daily) if stock_daily is not None else 0} 行")
                    
                    if stock_daily is not None and not stock_daily.is_empty():
                        logger.info(f"[Engine] 内存缓存命中: {len(stock_daily)} 行")
                        
                        self._build_factor_matrix_from_df(stock_daily)
                        
                        return {'daily': stock_daily}
                else:
                    logger.info(f"[Engine] 日期范围不匹配，从 LanceDB 加载")
            else:
                logger.info(f"[Engine] 缓存未加载，从 LanceDB 加载数据")
            
            try:
                logger.info(f"[Engine] 从 LanceDB 读取（列过滤）: {warmup_start_str} ~ {load_end_str}")
                stock_daily = manager.read('daily', start_date=warmup_start_str, end_date=load_end_str, fields=MINIMAL_FIELDS)
                
                if stock_daily is not None and not stock_daily.is_empty():
                    logger.info(f"[Engine] 从 LanceDB 读取成功: {len(stock_daily)} 行, 列数: {len(stock_daily.columns)}")
                    
                    self._build_factor_matrix_from_df(stock_daily)
                    
                    return {'daily': stock_daily}
                else:
                    logger.warning(f"[Engine] 从 LanceDB 读取数据为空")
            except Exception as e:
                logger.warning(f"[Engine] 从 LanceDB 读取失败: {e}")
        except Exception as e:
            logger.warning(f"[Engine] UnifiedDataManager 缓存未命中: {e}")
        
        if not hasattr(self.data_query, 'get_all_daily_data_for_period'):
            return None
        
        try:
            warmup_days = self.config.warmup_days
            hist_dates = self.data_query.get_trading_dates(
                (start_ts - timedelta(days=60)).strftime("%Y-%m-%d"),
                (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
            )
            
            if len(hist_dates) >= warmup_days:
                load_start_str = hist_dates[-warmup_days]
            elif hist_dates:
                load_start_str = hist_dates[0]
            else:
                load_start_str = start_ts.strftime("%Y-%m-%d")
            
            full_start = actual_start if 'actual_start' in locals() else load_start_str
            logger.info(f"[Engine] 预加载完整回测数据: {full_start} ~ {load_end_str}")
            self.data_query.preload_backtest_data(full_start, load_end_str)
            preloaded = getattr(self.data_query, '_preloaded_data', None)
            
            if preloaded is not None:
                logger.info(f"[Engine] 成功预加载 {len(preloaded)} 个数据点")
                
                self._build_factor_matrix(preloaded)
            
            return preloaded
            
        except Exception as e:
            logger.warning(f"[Engine] 预加载失败: {e}")
            return None
    
    def _build_factor_matrix(
        self,
        preloaded_data: Dict[str, 'pl.DataFrame']
    ) -> None:
        """
        构建三维因子矩阵
        
        将预加载数据转换为 (T, N, F) 三维矩阵
        """
        try:
            from core.backtest.factor_matrix import build_factor_matrix
            
            self._factor_matrix = build_factor_matrix(preloaded_data)
            
            logger.info(
                f"[Engine] 因子矩阵构建完成: "
                f"T={len(self._factor_matrix.dates)}, "
                f"N={len(self._factor_matrix.codes_str)}, "
                f"F={len(self._factor_matrix.factor_names)}"
            )
        except Exception as e:
            logger.warning(f"[Engine] 因子矩阵构建失败: {e}")
            self._factor_matrix = None
    
    def _build_factor_matrix_from_df(
        self,
        df: 'pl.DataFrame'
    ) -> None:
        """
        从单个 DataFrame 构建因子矩阵（零拷贝优化版）
        
        直接处理完整 DataFrame，无需按日期分区
        
        修复：计算 is_limit_up, is_limit_down, is_suspended 字段
        """
        try:
            from core.backtest.factor_matrix import FactorMatrixBuilder
            
            # 修复：计算涨停/跌停/停牌状态字段
            df_enhanced = self._compute_status_fields(df)
            
            builder = FactorMatrixBuilder()
            # FIX: 禁用缓存，确保使用计算后的状态字段
            self._factor_matrix = builder.build_from_single_dataframe(df_enhanced, use_cache=False)
            
            logger.info(
                f"[Engine] 因子矩阵构建完成: "
                f"T={len(self._factor_matrix.dates)}, "
                f"N={len(self._factor_matrix.codes_str)}, "
                f"F={len(self._factor_matrix.factor_names)}"
            )
        except Exception as e:
            logger.warning(f"[Engine] 因子矩阵构建失败: {e}")
            import traceback
            traceback.print_exc()
            self._factor_matrix = None
    
    def _compute_status_fields(self, df: 'pl.DataFrame') -> 'pl.DataFrame':
        """
        计算股票状态字段（涨停、跌停、停牌）
        
        原始数据中的 limit_up/limit_down 是价格，需要计算是否达到涨跌停
        FIX: 总是重新计算这些字段，即使原始数据中已经存在
        """
        df_enhanced = df
        
        # FIX: 总是重新计算 is_limit_up，即使原始数据中已经存在
        if 'limit_up' in df.columns and 'close' in df.columns:
            df_enhanced = df_enhanced.with_columns([
                (pl.col('close') >= pl.col('limit_up')).cast(pl.Float64).alias('is_limit_up')
            ])
        else:
            # 如果没有数据，默认全部为 0（未涨停）
            df_enhanced = df_enhanced.with_columns([
                pl.lit(0.0).cast(pl.Float64).alias('is_limit_up')
            ])
        
        # FIX: 总是重新计算 is_limit_down，即使原始数据中已经存在
        if 'limit_down' in df.columns and 'close' in df.columns:
            df_enhanced = df_enhanced.with_columns([
                (pl.col('close') <= pl.col('limit_down')).cast(pl.Float64).alias('is_limit_down')
            ])
        else:
            df_enhanced = df_enhanced.with_columns([
                pl.lit(0.0).cast(pl.Float64).alias('is_limit_down')
            ])
        
        # FIX: 总是重新计算 is_suspended，即使原始数据中已经存在
        if 'volume' in df.columns and 'close' in df.columns:
            df_enhanced = df_enhanced.with_columns([
                ((pl.col('volume') == 0) | (pl.col('close') == 0)).cast(pl.Float64).alias('is_suspended')
            ])
        else:
            df_enhanced = df_enhanced.with_columns([
                pl.lit(0.0).cast(pl.Float64).alias('is_suspended')
            ])
        
        return df_enhanced
    
    def _preload_factors(
        self,
        strategy: Any,
        preloaded_data: Optional[Dict[str, 'pl.DataFrame']]
    ) -> None:
        """
        预加载策略声明的因子
        
        核心功能：
        1. 直接从 daily 表读取因子列（ma5, ma10, ma20等）
        2. 从策略获取 required_factors
        3. 将因子数据传递给策略
        """
        if preloaded_data is None:
            return
        
        required_factors = getattr(strategy, 'required_factors', [])
        if not required_factors:
            return
        
        try:
            stock_daily_df = preloaded_data.get('daily')
            
            if stock_daily_df is None or len(stock_daily_df) == 0:
                logger.warning("[Engine] preloaded_data 中没有 daily 数据")
                return
            
            is_polars = hasattr(stock_daily_df, 'columns') and not isinstance(stock_daily_df, pd.DataFrame)
            
            if is_polars:
                trading_dates = sorted(stock_daily_df['trade_date'].unique().to_list())
                stock_codes = sorted(stock_daily_df['stock_code'].unique().to_list())
            else:
                trading_dates = sorted(stock_daily_df['trade_date'].unique().tolist())
                stock_codes = sorted(stock_daily_df['stock_code'].unique().tolist())
            
            logger.info(f"[Engine] 从 daily 预加载因子: {required_factors}")
            
            # 直接从 daily 读取因子列并构建矩阵
            factor_data = self._load_factors_from_daily(
                stock_daily_df, required_factors, trading_dates, stock_codes
            )
            
            if factor_data:
                self._preloaded_factors = factor_data
                logger.info(f"[Engine] 成功预加载 {len(factor_data)} 个因子: {list(factor_data.keys())}")
            else:
                self._preloaded_factors = {}
                logger.warning("[Engine] 未能从 daily 加载因子")
            
        except Exception as e:
            logger.warning(f"[Engine] 因子预加载失败: {e}")
            import traceback
            traceback.print_exc()
            self._preloaded_factors = {}
    
    def _load_factors_from_daily(
        self,
        stock_daily_df,
        required_factors: List[str],
        trading_dates: List[str],
        stock_codes: List[str]
    ) -> Optional[Dict[str, np.ndarray]]:
        """从 daily 表读取因子列并构建矩阵"""
        import polars as pl
        import pandas as pd
        
        is_polars = hasattr(stock_daily_df, 'columns') and not isinstance(stock_daily_df, pd.DataFrame)
        
        T = len(trading_dates)
        N = len(stock_codes)
        
        # 过滤只保留需要的因子列
        available_factors = [f for f in required_factors if f in stock_daily_df.columns]
        
        if not available_factors:
            logger.warning(f"[Engine] daily 中没有所需因子: {required_factors}")
            return None
        
        logger.info(f"[Engine] 可用因子: {available_factors}")
        
        # 构建日期和股票代码映射
        trading_dates_str = []
        for d in trading_dates:
            if hasattr(d, 'strftime'):
                trading_dates_str.append(d.strftime('%Y-%m-%d'))
            else:
                trading_dates_str.append(str(d)[:10])
        
        date_to_idx = {d: i for i, d in enumerate(trading_dates_str)}
        code_to_idx = {str(c).zfill(6): i for i, c in enumerate(stock_codes)}
        
        # 初始化因子矩阵
        factor_matrices = {f: np.full((T, N), np.nan, dtype=np.float32) for f in available_factors}
        
        # 转换日期格式用于匹配
        def normalize_date(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            elif isinstance(d, str):
                return d[:10]
            return str(d)[:10]
        
        if is_polars:
            stock_daily_df = stock_daily_df.with_columns([
                pl.col('trade_date').map_batches(
                    lambda col: col.map_elements(normalize_date, return_dtype=pl.Utf8)
                ).alias('trade_date_str'),
                pl.col('stock_code').cast(pl.Utf8).str.zfill(6).alias('stock_code_str')
            ])
            
            for factor in available_factors:
                matrix = factor_matrices[factor]
                
                # 获取该因子的数据
                factor_df = stock_daily_df.select(['trade_date_str', 'stock_code_str', factor]).drop_nulls(factor)
                
                if len(factor_df) == 0:
                    continue
                
                # 转换为 numpy 并填充矩阵
                dates = factor_df['trade_date_str'].to_list()
                codes = factor_df['stock_code_str'].to_list()
                values = factor_df[factor].to_numpy()
                
                for i in range(len(dates)):
                    d = dates[i]
                    c = codes[i]
                    if d in date_to_idx and c in code_to_idx:
                        t_idx = date_to_idx[d]
                        c_idx = code_to_idx[c]
                        matrix[t_idx, c_idx] = values[i]
                
                logger.info(f"[Engine] 因子 {factor}: 填充了 {np.sum(~np.isnan(matrix))} 个值")
        else:
            stock_daily_df = stock_daily_df.copy()
            stock_daily_df['trade_date_str'] = stock_daily_df['trade_date'].apply(normalize_date)
            stock_daily_df['stock_code_str'] = stock_daily_df['stock_code'].astype(str).str.zfill(6)
            
            for factor in available_factors:
                matrix = factor_matrices[factor]
                
                factor_df = stock_daily_df[['trade_date_str', 'stock_code_str', factor]].dropna(subset=[factor])
                
                if len(factor_df) == 0:
                    continue
                
                for _, row in factor_df.iterrows():
                    d = row['trade_date_str']
                    c = row['stock_code_str']
                    if d in date_to_idx and c in code_to_idx:
                        t_idx = date_to_idx[d]
                        c_idx = code_to_idx[c]
                        matrix[t_idx, c_idx] = row[factor]
                
                logger.info(f"[Engine] 因子 {factor}: 填充了 {np.sum(~np.isnan(matrix))} 个值")
        
        return factor_matrices if factor_matrices else None
    
    def _load_day_data(
        self,
        current_time: pd.Timestamp
    ) -> Tuple[Any, bool, Dict[str, Dict[str, Any]]]:
        """
        加载当日数据（优先使用因子矩阵）
        
        【性能优化】：
        1. 优先从因子矩阵获取（零拷贝切片）
        2. 回退到预加载数据
        3. 最后查询数据库
        """
        import time
        t0_total = time.perf_counter()
        
        date_str = current_time.strftime("%Y-%m-%d")
        use_pl = False
        stock_pool = None
        
        if self._factor_matrix is not None:
            t1 = time.perf_counter()
            result = self._load_day_data_from_matrix(date_str)
            logger.debug(f"[_load_day_data] 因子矩阵加载耗时: {(time.perf_counter()-t1)*1000:.1f}ms")
            return result
        
        if hasattr(self.data_query, 'get_stock_pool_from_preloaded'):
            t1 = time.perf_counter()
            preloaded_df = self.data_query.get_stock_pool_from_preloaded(date_str)
            logger.debug(f"[_load_day_data] 预加载数据查询耗时: {(time.perf_counter()-t1)*1000:.1f}ms")
            if preloaded_df is not None and len(preloaded_df) > 0:
                stock_pool = preloaded_df
                use_pl = True
        
        if stock_pool is None and hasattr(self.data_query, 'get_stock_pool_pl'):
            t1 = time.perf_counter()
            stock_pool = self.data_query.get_stock_pool_pl(date_str)
            logger.debug(f"[_load_day_data] Polars数据查询耗时: {(time.perf_counter()-t1)*1000:.1f}ms")
            if stock_pool is not None and hasattr(stock_pool, 'is_empty') and not stock_pool.is_empty():
                use_pl = True
        
        if stock_pool is None:
            t1 = time.perf_counter()
            stock_pool = self._get_stock_pool_at_time(current_time)
            logger.debug(f"[_load_day_data] 数据库查询耗时: {(time.perf_counter()-t1)*1000:.1f}ms")
        
        t1 = time.perf_counter()
        data_dict = {}
        if use_pl:
            needed_cols = [c for c in ['stock_code', 'close', 'open', 'adj_factor', 'total_mv', 
                                       'is_suspended', 'is_limit_up', 'is_limit_down'] 
                          if c in stock_pool.columns]
            data_dict = {
                str(row[0]): dict(zip(needed_cols, row))
                for row in stock_pool.select(needed_cols).iter_rows()
            }
        elif stock_pool is not None and hasattr(stock_pool, 'empty') and not stock_pool.empty:
            data_dict = stock_pool.set_index('stock_code').to_dict('index')
        
        logger.debug(f"[_load_day_data] dict构建耗时: {(time.perf_counter()-t1)*1000:.1f}ms, 总耗时: {(time.perf_counter()-t0_total)*1000:.1f}ms")
        
        return stock_pool, use_pl, data_dict
    
    def _load_day_data_from_matrix(
        self,
        date_str: str
    ) -> Tuple[np.ndarray, bool, Dict[str, Dict[str, Any]]]:
        """
        从因子矩阵加载当日数据
        
        返回：
            factor_slice: (N, F) 二维矩阵
            use_pl: 固定为 False
            data_dict: 用于交易执行的字典（包含每只股票的数据）
        """
        fm = self._factor_matrix
        date_str_normalized = date_str
        if date_str not in fm.date_to_idx:
            if ' ' in date_str:
                date_str_normalized = date_str.split(' ')[0]
            else:
                date_str_normalized = date_str + ' 00:00:00'
        
        date_idx = fm.date_to_idx.get(date_str_normalized, -1)
        
        if date_idx < 0:
            return None, False, {}
        
        factor_slice = fm.values[date_idx, :, :]
        
        import time as time_module
        t0 = time_module.perf_counter()
        
        # FIX: 构建完整的 data_dict，包含每只股票的 close 价格
        data_dict = self._build_data_dict_fast(factor_slice, fm)
        
        logger.debug(f"[_load_day_data_from_matrix] _build_data_dict_fast耗时: {(time_module.perf_counter()-t0)*1000:.1f}ms")
        
        return factor_slice, False, data_dict
    
    def _build_data_dict_fast(
        self,
        factor_slice: np.ndarray,
        fm: Any
    ) -> Dict:
        """
        快速构建data_dict（NumPy结构化数组优化版）
        
        性能优化：
        1. 使用NumPy向量化操作代替Python循环
        2. 使用结构化数组替代字典
        """
        factor_names = fm.factor_names
        codes = fm.codes_str
        N = len(codes)
        
        factor_idx = {name: i for i, name in enumerate(factor_names)}
        
        # 创建NumPy结构化数组（零拷贝）
        dtype = np.dtype([
            ('open', np.float64),
            ('close', np.float64),
            ('high', np.float64),
            ('low', np.float64),
            ('volume', np.float64),
            ('amount', np.float64),
            ('total_mv', np.float64),
            ('float_mv', np.float64),
            ('turnover_rate', np.float64),
            ('volume_ratio', np.float64),
            ('is_limit_up', np.int8),
            ('is_limit_down', np.int8),
            ('is_suspended', np.int8),
            ('is_st', np.int8),
            ('adj_factor', np.float64),
            ('prev_close', np.float64),
        ])
        
        market_data = np.zeros(N, dtype=dtype)
        
        # 向量化填充
        for fname, npname in [
            ('open', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'),
            ('volume', 'volume'), ('amount', 'amount'), ('total_mv', 'total_mv'),
            ('float_mv', 'float_mv'), ('turnover_rate', 'turnover_rate'),
            ('volume_ratio', 'volume_ratio'), ('adj_factor', 'adj_factor'),
            ('prev_close', 'prev_close'), ('is_limit_up', 'is_limit_up'),
            ('is_limit_down', 'is_limit_down'), ('is_suspended', 'is_suspended'),
            ('is_st', 'is_st')
        ]:
            if fname in factor_idx:
                col = factor_slice[:, factor_idx[fname]]
                col = np.where(np.isnan(col), 0, col)
                if npname in ['is_limit_up', 'is_limit_down', 'is_suspended', 'is_st']:
                    market_data[npname] = col.astype(np.int8)
                else:
                    market_data[npname] = col
        
        # 返回结构化数组 + 代码列表（避免字典推导）
        return {
            '_codes': codes,
            '_market_data': market_data,
            '_factor_slice': factor_slice,
        }
    
    def _build_market_df_from_matrix(
        self,
        factor_slice: np.ndarray,
        fm: Any
    ):
        """
        直接从因子矩阵构建 Polars DataFrame（避免中间字典转换）
        """
        factor_names = fm.factor_names
        codes = fm.codes_str
        N = len(codes)
        
        factor_idx = {name: i for i, name in enumerate(factor_names)}
        
        def get_col(name, default):
            idx = factor_idx.get(name, -1)
            if idx >= 0:
                col = factor_slice[:, idx]
                return np.nan_to_num(col, nan=default)
            return np.full(N, default)
        
        open_col = get_col('open', 0.0).astype(np.float64)
        close_col = get_col('close', 0.0).astype(np.float64)
        is_limit_up_col = get_col('is_limit_up', 0).astype(bool)
        is_limit_down_col = get_col('is_limit_down', 0).astype(bool)
        is_suspended_col = get_col('is_suspended', 0).astype(bool)
        total_mv_col = get_col('total_mv', 0.0).astype(np.float64)
        adj_factor_col = get_col('adj_factor', 1.0).astype(np.float64)
        
        return pl.DataFrame({
            'code': codes,
            'open': open_col,
            'close': close_col,
            'is_suspended': is_suspended_col,
            'is_limit_up': is_limit_up_col,
            'is_limit_down': is_limit_down_col,
            'adj_factor': adj_factor_col,
            'total_mv': total_mv_col
        })
    
    def _get_stock_pool_at_time(self, date: Union[str, pd.Timestamp]) -> pd.DataFrame:
        """获取指定日期的股票池（带缓存）"""
        if isinstance(date, pd.Timestamp):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = str(date)
        
        # 缓存检查
        if date_str in self._stock_pool_cache:
            self._cache_order.remove(date_str)
            self._cache_order.append(date_str)
            return self._stock_pool_cache[date_str]
        
        # 加载数据
        try:
            result = self.data_query.get_stock_pool(date_str)
            self._stock_pool_cache[date_str] = result
            self._cache_order.append(date_str)
            
            # LRU淘汰
            if len(self._stock_pool_cache) > self._cache_max_size:
                oldest = self._cache_order.pop(0)
                self._stock_pool_cache.pop(oldest, None)
            
            return result
        except Exception as e:
            logger.error(f"获取股票池失败 {date_str}: {e}")
            return pd.DataFrame()
    
    def _set_strategy_context(
        self,
        strategy: Any,
        current_time: pd.Timestamp,
        portfolio: Dict[str, int],
        cash: float
    ):
        """设置策略运行时上下文"""
        if hasattr(strategy, 'set_runtime_context'):
            strategy.set_runtime_context(
                current_date=current_time.strftime("%Y-%m-%d"),
                portfolio=portfolio,
                cash=cash
            )
    
    def _generate_signals(
        self,
        strategy: Any,
        current_time: pd.Timestamp,
        stock_pool: Any,
        preloaded_data: Optional[Dict],
        idx: int,
        time_series: List[pd.Timestamp]
    ) -> Dict[str, Any]:
        """生成交易信号"""
        # 检查是否是配置化策略
        if isinstance(strategy, dict) or hasattr(strategy, 'to_dict'):
            return self._generate_signals_from_config(strategy, current_time, stock_pool)
        
        # 检查向量化模式
        if hasattr(strategy, 'generate_signals_vectorized') and preloaded_data is not None:
            if idx == 1:
                # FIX: 传递 current_time 给 _generate_vectorized_signals
                return self._generate_vectorized_signals(strategy, preloaded_data, time_series, current_time)
            elif self._vectorized_mode:
                return self._get_vectorized_signals_for_day(current_time)
        
        # 传统模式
        if hasattr(strategy, 'generate_signals'):
            stock_pool_for_strategy = stock_pool
            if hasattr(stock_pool, 'to_pandas'):
                stock_pool_for_strategy = stock_pool.to_pandas()
            elif isinstance(stock_pool, np.ndarray):
                return {}
            return strategy.generate_signals(
                current_date=current_time.strftime("%Y-%m-%d"),
                stock_pool_today=stock_pool_for_strategy,
                data_query=self.data_query
            )
        
        return {}
    
    def _generate_signals_from_config(
        self,
        config: Any,
        current_time: pd.Timestamp,
        stock_pool: Any
    ) -> Dict[str, Any]:
        """从配置生成信号（待实现）"""
        # TODO: 集成配置化策略系统
        logger.warning("配置化策略系统尚未实现")
        return {}
    
    def _generate_vectorized_signals(
        self,
        strategy: Any,
        preloaded_data: Dict,
        time_series: List[pd.Timestamp],
        current_time: pd.Timestamp
    ) -> Dict[str, Any]:
        """生成向量化信号 - 使用矩阵缓存管理器"""
        import time
        t_start = time.perf_counter()
        
        # FIX: 使用 time_series 作为 trading_dates，确保与回测范围一致
        backtest_dates = [ts.strftime("%Y-%m-%d") for ts in time_series]
        
        if 'daily' in preloaded_data:
            stock_daily = preloaded_data['daily']
            all_codes = stock_daily['stock_code'].unique().to_list()
            # FIX: 确保股票代码是6位字符串格式
            stock_codes_list = sorted([str(c).zfill(6) for c in all_codes])
        else:
            all_codes = set()
            for df in preloaded_data.values():
                if df is not None and len(df) > 0:
                    if hasattr(df, 'is_empty'):
                        all_codes.update(df['stock_code'].unique().to_list())
                    else:
                        all_codes.update(df['stock_code'].unique())
            # FIX: 确保股票代码是6位字符串格式
            stock_codes_list = sorted([str(c).zfill(6) for c in all_codes])
        
        # FIX: 优先使用 self._factor_matrix，确保信号生成和交易执行使用相同的数据
        if self._factor_matrix is not None:
            fm = self._factor_matrix
            factor_idx = {name: i for i, name in enumerate(fm.factor_names)}
            
            # 检查因子矩阵是否包含所需字段
            open_idx = factor_idx.get('open', -1)
            high_idx = factor_idx.get('high', -1)
            low_idx = factor_idx.get('low', -1)
            close_idx = factor_idx.get('close', -1)
            
            # 前复权价格索引
            open_adj_idx = factor_idx.get('open_adj', -1)
            high_adj_idx = factor_idx.get('high_adj', -1)
            low_adj_idx = factor_idx.get('low_adj', -1)
            close_adj_idx = factor_idx.get('close_adj', -1)
            
            if open_idx >= 0 and high_idx >= 0 and low_idx >= 0 and close_idx >= 0:
                # 检查因子矩阵的日期和股票代码是否匹配
                if len(fm.codes_str) == len(stock_codes_list):
                    # 不复权价格矩阵（用于交易执行）
                    price_matrix = np.stack([
                        fm.values[:, :, open_idx],
                        fm.values[:, :, high_idx],
                        fm.values[:, :, low_idx],
                        fm.values[:, :, close_idx]
                    ], axis=2)
                    
                    # 前复权价格矩阵（用于指标计算）
                    # 如果有前复权价格字段，使用它；否则使用不复权价格
                    if open_adj_idx >= 0 and close_adj_idx >= 0:
                        price_matrix_adj = np.stack([
                            fm.values[:, :, open_adj_idx],
                            fm.values[:, :, high_adj_idx] if high_adj_idx >= 0 else fm.values[:, :, high_idx],
                            fm.values[:, :, low_adj_idx] if low_adj_idx >= 0 else fm.values[:, :, low_idx],
                            fm.values[:, :, close_adj_idx]
                        ], axis=2)
                    else:
                        price_matrix_adj = price_matrix
                    
                    # 使用因子矩阵的完整日期列表
                    trading_dates = fm.dates
                    T = len(trading_dates)
                    logger.info(f"[_generate_vectorized_signals] 使用 self._factor_matrix (完整日期: {len(fm.dates)}天)")
                    t_matrix_build = (time.perf_counter() - t_start) * 1000
                    t_prepare_data = 0
                else:
                    # 回退到 MatrixCacheManager
                    T = len(backtest_dates)
                    N = len(stock_codes_list)
                    price_matrix = self._build_price_matrix_from_cache(
                        preloaded_data, backtest_dates, stock_codes_list, T, N
                    )
                    price_matrix_adj = price_matrix
                    trading_dates = backtest_dates
                    t_matrix_build = (time.perf_counter() - t_start) * 1000
                    t_prepare_data = t_matrix_build
            else:
                # 回退到 MatrixCacheManager
                T = len(backtest_dates)
                N = len(stock_codes_list)
                price_matrix = self._build_price_matrix_from_cache(
                    preloaded_data, backtest_dates, stock_codes_list, T, N
                )
                price_matrix_adj = price_matrix
                trading_dates = backtest_dates
                t_matrix_build = (time.perf_counter() - t_start) * 1000
                t_prepare_data = t_matrix_build
        else:
            # 回退到 MatrixCacheManager
            T = len(backtest_dates)
            N = len(stock_codes_list)
            price_matrix = self._build_price_matrix_from_cache(
                preloaded_data, backtest_dates, stock_codes_list, T, N
            )
            price_matrix_adj = price_matrix
            trading_dates = backtest_dates
            t_matrix_build = (time.perf_counter() - t_start) * 1000
            t_prepare_data = t_matrix_build
        
        t_matrix_built = time.perf_counter()
        
        # [声明式因子系统] 注入预加载的因子到策略
        if hasattr(self, '_preloaded_factors') and self._preloaded_factors:
            strategy.factors = self._preloaded_factors
            for factor_name, matrix in self._preloaded_factors.items():
                setattr(strategy, factor_name, matrix)
        
        # 调用策略的向量化信号生成
        # 传递两个价格矩阵：
        # - price_matrix: 不复权价格（用于交易）
        # - price_matrix_adj: 前复权价格（用于指标计算）
        signal_matrix = strategy.generate_signals_vectorized(
            price_matrix=price_matrix,
            trading_dates=trading_dates,
            stock_codes=stock_codes_list,
            data_query=self.data_query,
            preloaded_data=preloaded_data,
            price_matrix_adj=price_matrix_adj
        )
        
        t_signals_done = time.perf_counter()
        
        # 保存向量化状态
        self._vectorized_mode = True
        self._signal_matrix = signal_matrix
        self._stock_codes_list = stock_codes_list
        # FIX: _date_to_idx 基于完整日期构建（包含 warmup）
        # 这样 _get_vectorized_signals_for_day 可以正确获取任何日期的信号
        # 标准化日期格式为 YYYY-MM-DD（不含时间），与 _backtest_dates 保持一致
        trading_dates_str = [d.split(' ')[0] if isinstance(d, str) and ' ' in d else str(d)[:10] for d in trading_dates]
        self._date_to_idx = {d: i for i, d in enumerate(trading_dates_str)}
        # FIX: 保存回测日期范围，用于过滤信号
        self._backtest_dates = set(backtest_dates)
        
        # DEBUG
        # 性能日志
        matrix_time = (t_matrix_built - t_start) * 1000
        signal_time = (t_signals_done - t_matrix_built) * 1000
        total_time = (t_signals_done - t_start) * 1000
        logger.info(f"[_generate_vectorized_signals] matrix_build: {t_matrix_build:.1f}ms, strategy: {signal_time:.1f}ms, 总计: {total_time:.1f}ms")
        
        # FIX: 不返回第一天的信号，让主循环统一处理所有天数
        # 这样可以避免第一天的 equity curve 被重复添加
        return self._get_vectorized_signals_for_day(current_time)
    
    def _build_price_matrix_fallback(
        self,
        preloaded_data: Dict,
        trading_dates: List[str],
        stock_codes_list: List[str]
    ) -> np.ndarray:
        """回退方案：从 DataFrame 构建价格矩阵（支持 Polars）"""
        import polars as pl
        
        T = len(trading_dates)
        N = len(stock_codes_list)
        
        price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)
        
        code_to_idx = {code: i for i, code in enumerate(stock_codes_list)}
        date_to_idx = {date: i for i, date in enumerate(trading_dates)}
        
        if 'daily' in preloaded_data:
            stock_daily = preloaded_data['daily']
            
            df_with_idx = stock_daily.select(['trade_date', 'stock_code', 'open', 'high', 'low', 'close']).with_columns([
                pl.col('trade_date').cast(pl.Utf8).replace_strict(date_to_idx, default=None).alias('date_idx'),
                pl.col('stock_code').cast(pl.Utf8).str.strip_chars().replace_strict(code_to_idx, default=None).alias('code_idx')
            ])
            
            df_with_idx = df_with_idx.filter(
                pl.col('date_idx').is_not_null() & pl.col('code_idx').is_not_null()
            )
            
            if len(df_with_idx) > 0:
                t_indices = df_with_idx['date_idx'].to_numpy().astype(np.int32)
                n_indices = df_with_idx['code_idx'].to_numpy().astype(np.int32)
                
                price_matrix[t_indices, n_indices, 0] = df_with_idx['open'].to_numpy()
                price_matrix[t_indices, n_indices, 1] = df_with_idx['high'].to_numpy()
                price_matrix[t_indices, n_indices, 2] = df_with_idx['low'].to_numpy()
                price_matrix[t_indices, n_indices, 3] = df_with_idx['close'].to_numpy()
        else:
            first_df = next(iter(preloaded_data.values())) if preloaded_data else None
            is_polars = hasattr(first_df, 'columns') and not isinstance(first_df, pd.DataFrame)
            
            if is_polars:
                all_data_list = []
                for date_str, df_day in preloaded_data.items():
                    if df_day is not None and hasattr(df_day, 'is_empty') and not df_day.is_empty() and date_str in date_to_idx:
                        df_copy = df_day.select(['stock_code', 'open', 'high', 'low', 'close']).clone()
                        df_copy = df_copy.with_columns(pl.lit(date_to_idx[date_str]).alias('date_idx'))
                        all_data_list.append(df_copy)
                
                if all_data_list:
                    all_data_pl = pl.concat(all_data_list)
                    all_data_pl = all_data_pl.with_columns(
                        pl.col('stock_code').cast(pl.Utf8).str.strip_chars().replace_strict(code_to_idx, default=None).alias('code_idx')
                    )
                    all_data_pl = all_data_pl.filter(pl.col('code_idx').is_not_null())
                    
                    if len(all_data_pl) > 0:
                        t_indices = all_data_pl['date_idx'].to_numpy().astype(np.int32)
                        n_indices = all_data_pl['code_idx'].to_numpy().astype(np.int32)
                        
                        price_matrix[t_indices, n_indices, 0] = all_data_pl['open'].to_numpy()
                        price_matrix[t_indices, n_indices, 1] = all_data_pl['high'].to_numpy()
                        price_matrix[t_indices, n_indices, 2] = all_data_pl['low'].to_numpy()
                        price_matrix[t_indices, n_indices, 3] = all_data_pl['close'].to_numpy()
            else:
                all_data_list = []
                for date_str, df_day in preloaded_data.items():
                    if df_day is None:
                        continue
                    if isinstance(df_day, np.ndarray):
                        if df_day.size == 0:
                            continue
                    elif hasattr(df_day, 'empty') and df_day.empty:
                        continue
                    if date_str not in date_to_idx:
                        continue
                    df_copy = df_day[['stock_code', 'open', 'high', 'low', 'close']].copy()
                    df_copy['date_idx'] = date_to_idx[date_str]
                    all_data_list.append(df_copy)
                
                if all_data_list:
                    all_data_df = pd.concat(all_data_list, ignore_index=True)
                    all_data_df['stock_code'] = all_data_df['stock_code'].astype(str).str.strip()
                    all_data_df['code_idx'] = all_data_df['stock_code'].map(code_to_idx)
                    all_data_df = all_data_df.dropna(subset=['code_idx'])
                    
                    if not all_data_df.empty:
                        all_data_df['code_idx'] = all_data_df['code_idx'].astype(int)
                        t_indices = all_data_df['date_idx'].values.astype(int)
                        n_indices = all_data_df['code_idx'].values
                        
                        price_matrix[t_indices, n_indices, 0] = all_data_df['open'].values
                        price_matrix[t_indices, n_indices, 1] = all_data_df['high'].values
                        price_matrix[t_indices, n_indices, 2] = all_data_df['low'].values
                        price_matrix[t_indices, n_indices, 3] = all_data_df['close'].values
        
        return price_matrix
    
    def _build_price_matrix_from_cache(
        self,
        preloaded_data: Dict,
        trading_dates: List[str],
        stock_codes_list: List[str],
        T: int,
        N: int
    ) -> np.ndarray:
        """从 MatrixCacheManager 构建价格矩阵"""
        from core.backtest.matrix_cache_manager import get_matrix_cache_manager
        
        cache_manager = get_matrix_cache_manager()
        start_date = trading_dates[0] if trading_dates else ""
        end_date = trading_dates[-1] if trading_dates else ""
        
        cached_data = cache_manager.load_matrix_mmap(start_date, end_date, stock_codes_list)
        
        # 验证缓存形状是否匹配当前回测参数
        cache_valid = False
        if cached_data is not None:
            cached_dates = cached_data.get('trading_dates', [])
            cached_codes = cached_data.get('stock_codes', [])
            if len(cached_dates) == T and len(cached_codes) == N:
                cache_valid = True
        
        if cache_valid:
            # 缓存命中且形状匹配 - 使用内存映射的矩阵
            matrices = cached_data['matrices']
            price_matrix = np.stack([
                matrices['open'],      # 0: open
                matrices['high'],      # 1: high
                matrices['low'],       # 2: low
                matrices['close']      # 3: close
            ], axis=2)
            logger.info(f"[_build_price_matrix_from_cache] 矩阵缓存命中 (内存映射)")
            return price_matrix
        else:
            # 缓存未命中 - 构建矩阵并保存到缓存
            logger.info(f"[_build_price_matrix_from_cache] 矩阵缓存未命中，开始构建...")
            
            # 构建矩阵并保存
            cache_result = cache_manager.build_and_save_matrix(
                preloaded_data, trading_dates, stock_codes_list
            )
            
            if cache_result is not None:
                # 使用刚构建的矩阵
                matrices = cache_result['matrices']
                price_matrix = np.stack([
                    matrices['open'],
                    matrices['high'],
                    matrices['low'],
                    matrices['close']
                ], axis=2)
                return price_matrix
            else:
                # 缓存已存在（在 build_and_save_matrix 中检查），重新加载
                cached_data = cache_manager.load_matrix_mmap(start_date, end_date, stock_codes_list)
                if cached_data:
                    matrices = cached_data['matrices']
                    price_matrix = np.stack([
                        matrices['open'],
                        matrices['high'],
                        matrices['low'],
                        matrices['close']
                    ], axis=2)
                    return price_matrix
                else:
                    # 回退到原始构建方式
                    return self._build_price_matrix_fallback(
                        preloaded_data, trading_dates, stock_codes_list
                    )
    
    def _get_vectorized_signals_for_day(self, current_time: pd.Timestamp) -> Dict[str, Any]:
        """从向量化矩阵获取指定日期的信号（优化版）"""
        current_date_str = current_time.strftime("%Y-%m-%d")
        
        # FIX: 检查当前日期是否在回测日期范围内
        # 如果是 warmup 日期，不生成信号
        if hasattr(self, '_backtest_dates') and current_date_str not in self._backtest_dates:
            return {}
        
        t_idx = self._date_to_idx.get(current_date_str, -1)
        
        if t_idx < 0 or self._signal_matrix is None:
            return {}
        
        # FIX: 检查索引是否越界
        if t_idx >= self._signal_matrix.shape[0]:
            return {}
        
        signals = {}
        day_signals = self._signal_matrix[t_idx, :]
        
        # FIX: 支持两种信号格式：1=买入, -1或2=卖出
        buy_mask = day_signals == 1
        sell_mask = (day_signals == -1) | (day_signals == 2)
        
        if buy_mask.any():
            buy_indices = np.where(buy_mask)[0]
            for idx in buy_indices:
                signals[self._stock_codes_list[idx]] = {'action': 'buy', 'indicators': {}}
        
        if sell_mask.any():
            sell_indices = np.where(sell_mask)[0]
            for idx in sell_indices:
                signals[self._stock_codes_list[idx]] = {'action': 'sell', 'indicators': {}}
        
        return signals
    
    def _execute_trades(
        self,
        current_time: pd.Timestamp,
        stock_pool: Any,
        signals: Dict[str, Any],
        portfolio: Dict[str, int],
        cash: float,
        position_info: Dict[str, Dict[str, Any]],
        data_dict: Dict[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, int], float, List[TradeRecord]]:
        """
        执行交易 - 向量化优化版本
        
        性能优化：
        1. 使用 Polars DataFrame 批量处理信号
        2. 向量化计算交易参数（佣金、税费、盈亏）
        3. 减少循环次数，O(n) -> O(1) 批量操作
        """
        new_portfolio = portfolio.copy()
        new_cash = cash
        trades = []
        date_str = current_time.strftime("%Y-%m-%d")
        
        if not signals:
            return new_portfolio, new_cash, trades
        
        # =========================================================================
        # [向量化优化] 将信号和数据转换为 DataFrame 批量处理
        # =========================================================================
        if POLARS_AVAILABLE and len(signals) > 5:
            return self._execute_trades_vectorized(
                current_time, signals, portfolio, cash, position_info, data_dict, date_str
            )
        
        # 回退到原始逻辑（小规模信号）
        signal_data = {code: data_dict.get(code, {}) for code in signals.keys() if code in data_dict}
        
        # 阶段1: 处理卖出
        for code, signal in signals.items():
            sig_type = signal.get('action') if isinstance(signal, dict) else signal
            if sig_type not in ('sell', 'exit'):
                continue

            current_position = new_portfolio.get(code, 0)
            if current_position <= 0:
                continue

            if code not in signal_data:
                continue

            data = signal_data[code]
            price = float(data.get('open', 0))
            is_suspended = bool(data.get('is_suspended', 0))
            is_limit_down = bool(data.get('is_limit_down', 0))

            if price <= 0:
                self._rejected_stats.invalid_price += 1
                continue
            if is_suspended:
                self._rejected_stats.suspended += 1
                continue
            if is_limit_down:
                self._rejected_stats.limit_down += 1
                continue

            # 应用滑点：卖出按 (1 - slippage_rate) 减价
            slippage = self.config.slippage_rate
            filled_price = price * (1.0 - slippage)
            slippage_cost_per_share = price * slippage
            self._slippage_cost_total += current_position * slippage_cost_per_share

            # 执行卖出
            revenue = current_position * filled_price
            commission = max(revenue * self.config.commission_rate, self.config.min_commission)
            tax = revenue * self.config.sell_tax
            net_revenue = revenue - commission - tax

            # 计算盈亏
            pos_data = position_info.get(code, {})
            avg_cost = pos_data.get('cost', filled_price)
            entry_date = pos_data.get('entry_date', date_str)
            cost_basis = avg_cost * current_position
            profit_loss = net_revenue - cost_basis
            roi = (profit_loss / cost_basis * 100) if cost_basis > 0 else 0

            # 计算持有天数
            try:
                d1 = datetime.strptime(entry_date, "%Y-%m-%d")
                d2 = datetime.strptime(date_str, "%Y-%m-%d")
                holding_days = (d2 - d1).days
            except:
                holding_days = 0

            new_cash += net_revenue
            del new_portfolio[code]
            if code in position_info:
                del position_info[code]

            position_id = f"{entry_date}-{code}"

            trades.append(TradeRecord(
                date=date_str,
                code=code,
                action="sell",
                shares=current_position,
                price=filled_price,
                amount=net_revenue,
                commission=commission,
                tax=tax,
                profit_loss=profit_loss,
                roi=roi,
                entry_price=avg_cost,
                entry_date=entry_date,
                exit_price=filled_price,
                exit_date=date_str,
                holding_days=holding_days,
                position_id=position_id,
                indicators=signal.get('indicators', {}) if isinstance(signal, dict) else {}
            ))

        # 阶段2: 处理买入
        buy_signals = {code: sig for code, sig in signals.items()
                      if (sig.get('action') if isinstance(sig, dict) else sig) in ('buy', 'enter')}

        # 检查持仓限制
        current_positions_count = len(new_portfolio)
        max_positions = self.config.max_positions

        if max_positions is not None and current_positions_count >= max_positions:
            buy_signals = {}
        elif max_positions is not None:
            can_buy = max_positions - current_positions_count
            buy_signals = dict(list(buy_signals.items())[:can_buy])

        # 检查单日买入限制
        max_stocks_per_day = self.config.max_stocks_per_day
        if max_stocks_per_day is not None:
            buy_signals = dict(list(buy_signals.items())[:max_stocks_per_day])

        for code, signal in buy_signals.items():
            if new_portfolio.get(code, 0) > 0:
                continue

            if code not in signal_data:
                continue

            data = signal_data[code]
            price = float(data.get('open', 0))
            is_suspended = bool(data.get('is_suspended', 0))
            is_limit_up = bool(data.get('is_limit_up', 0))
            is_st = bool(data.get('is_st', 0))
            volume = float(data.get('volume', 0))

            if price <= 0:
                self._rejected_stats.invalid_price += 1
                continue
            if is_suspended:
                self._rejected_stats.suspended += 1
                continue
            if is_limit_up:
                self._rejected_stats.limit_up += 1
                continue
            if self.config.exclude_st and is_st:
                self._rejected_stats.st += 1
                continue

            # 计算买入金额
            target_investment = new_cash * self.config.position_ratio
            if target_investment > new_cash:
                target_investment = new_cash

            if target_investment < self.config.min_trade_amount:
                self._rejected_stats.insufficient_cash += 1
                continue

            # 应用滑点：买入按 (1 + slippage_rate) 加价
            slippage = self.config.slippage_rate
            filled_price = price * (1.0 + slippage)
            slippage_cost_per_share = price * slippage

            # 计算股数（100股整数倍）
            shares = int(target_investment / (filled_price * (1 + self.config.commission_rate)))
            shares = (shares // 100) * 100

            if shares < 100:
                self._rejected_stats.insufficient_cash += 1
                continue

            # 成交量约束：单笔买入股数 <= 当日成交量 × volume_cap_ratio
            if volume > 0 and self.config.volume_cap_ratio > 0:
                max_shares = int(volume * self.config.volume_cap_ratio)
                max_shares = (max_shares // 100) * 100
                if shares > max_shares:
                    if max_shares < 100:
                        self._rejected_stats.volume += 1
                        continue
                    shares = max_shares

            cost = shares * filled_price
            commission = max(cost * self.config.commission_rate, self.config.min_commission)
            total_outlay = cost + commission

            if total_outlay <= new_cash:
                new_portfolio[code] = shares
                new_cash -= total_outlay
                self._slippage_cost_total += shares * slippage_cost_per_share

                position_id = f"{date_str}-{code}"

                position_info[code] = {
                    'cost': total_outlay / shares,
                    'entry_date': date_str,
                    'position_id': position_id
                }

                trades.append(TradeRecord(
                    date=date_str,
                    code=code,
                    action="buy",
                    shares=shares,
                    price=filled_price,
                    amount=total_outlay,
                    commission=commission,
                    holding_days=0,
                    position_id=position_id,
                    indicators=signal.get('indicators', {}) if isinstance(signal, dict) else {}
                ))
            else:
                self._rejected_stats.insufficient_cash += 1

        return new_portfolio, new_cash, trades
    
    def _execute_trades_vectorized(
        self,
        current_time: pd.Timestamp,
        signals: Dict[str, Any],
        portfolio: Dict[str, int],
        cash: float,
        position_info: Dict[str, Dict[str, Any]],
        data_dict: Dict[str, Dict[str, Any]],
        date_str: str
    ) -> Tuple[Dict[str, int], float, List[TradeRecord]]:
        """
        向量化交易执行 - 使用 Polars 批量处理
        
        性能优势：
        - 批量筛选可交易信号
        - 向量化计算佣金、税费、盈亏
        - 减少循环开销
        """
        new_portfolio = portfolio.copy()
        new_cash = cash
        trades = []
        
        signal_rows = []
        for code, signal in signals.items():
            sig_type = signal.get('action') if isinstance(signal, dict) else signal
            if sig_type in ('buy', 'enter', 'sell', 'exit'):
                signal_rows.append({
                    'code': code,
                    'action': 'sell' if sig_type in ('sell', 'exit') else 'buy',
                    'indicators': signal.get('indicators', {}) if isinstance(signal, dict) else {}
                })
        
        if not signal_rows:
            return new_portfolio, new_cash, trades

        signals_df = pl.DataFrame(signal_rows)

        if self._factor_matrix is not None and isinstance(data_dict, dict) and '_factor_slice' in data_dict:
            factor_slice = data_dict['_factor_slice']
            fm = self._factor_matrix
            market_df = self._build_market_df_from_matrix(factor_slice, fm)
        else:
            market_rows = []
            for code, data in data_dict.items():
                market_rows.append({
                    'code': code,
                    'open': float(data.get('open') or 0),
                    'close': float(data.get('close') or 0),
                    'is_suspended': bool(data.get('is_suspended') or 0),
                    'is_limit_up': bool(data.get('is_limit_up') or 0),
                    'is_limit_down': bool(data.get('is_limit_down') or 0),
                    'is_st': bool(data.get('is_st') or 0),
                    'volume': float(data.get('volume') or 0),
                    'adj_factor': float(data.get('adj_factor') or 1.0),
                    'total_mv': float(data.get('total_mv') or 0)
                })

            market_df = pl.DataFrame(market_rows)
        
        # =========================================================================
        # Step 3: 构建持仓 DataFrame
        # =========================================================================
        position_rows = []
        for code, shares in portfolio.items():
            pos_data = position_info.get(code, {})
            position_rows.append({
                'code': code,
                'shares': shares,
                'cost': pos_data.get('cost', 0),
                'entry_date': pos_data.get('entry_date', date_str)
            })
        
        positions_df = pl.DataFrame(position_rows) if position_rows else pl.DataFrame({
            'code': [], 'shares': [], 'cost': [], 'entry_date': []
        }).with_columns([
            pl.col('shares').cast(pl.Int64),
            pl.col('cost').cast(pl.Float64),
            pl.col('entry_date').cast(pl.Utf8)
        ])
        
        # =========================================================================
        # Step 4: 向量化处理卖出信号
        # =========================================================================
        sell_signals = signals_df.filter(pl.col('action') == 'sell')

        if not sell_signals.is_empty() and not positions_df.is_empty():
            # 关联持仓数据
            sell_with_position = sell_signals.join(
                positions_df, on='code', how='inner'
            ).join(
                market_df.select(['code', 'open', 'is_suspended', 'is_limit_down']),
                on='code', how='inner'
            )

            # 统计被拒绝的原因
            try:
                self._rejected_stats.suspended += int(
                    sell_with_position.filter(pl.col('is_suspended') == True).height
                )
                self._rejected_stats.limit_down += int(
                    sell_with_position.filter(pl.col('is_limit_down') == True).height
                )
                self._rejected_stats.invalid_price += int(
                    sell_with_position.filter(pl.col('open') <= 0).height
                )
            except Exception:
                pass

            # 筛选可卖出的股票
            sellable = sell_with_position.filter(
                (pl.col('shares') > 0) &
                (pl.col('open') > 0) &
                (pl.col('is_suspended') == False) &
                (pl.col('is_limit_down') == False)
            )

            if not sellable.is_empty():
                # 应用滑点：卖出按 (1 - slippage_rate) 减价
                slippage = self.config.slippage_rate
                sellable = sellable.with_columns([
                    (pl.col('open') * (1.0 - slippage)).alias('filled_price'),
                ])
                # 累计滑点成本
                try:
                    slippage_sum = (sellable['open'] * slippage * sellable['shares']).sum()
                    self._slippage_cost_total += float(slippage_sum)
                except Exception:
                    pass

                # 向量化计算卖出参数
                sellable = sellable.with_columns([
                    (pl.col('shares') * pl.col('filled_price')).alias('revenue'),
                ]).with_columns([
                    pl.max_horizontal([
                        pl.col('revenue') * self.config.commission_rate,
                        self.config.min_commission
                    ]).alias('commission'),
                    (pl.col('revenue') * self.config.sell_tax).alias('tax'),
                ]).with_columns([
                    (pl.col('revenue') - pl.col('commission') - pl.col('tax')).alias('net_revenue'),
                    (pl.col('cost') * pl.col('shares')).alias('cost_basis'),
                ]).with_columns([
                    (pl.col('net_revenue') - pl.col('cost_basis')).alias('profit_loss'),
                ]).with_columns([
                    pl.when(pl.col('cost_basis') > 0)
                      .then(pl.col('profit_loss') / pl.col('cost_basis') * 100)
                      .otherwise(0).alias('roi')
                ])

                # 计算持有天数
                current_date = datetime.strptime(date_str, "%Y-%m-%d")
                sellable = sellable.with_columns([
                    pl.col('entry_date').map_elements(
                        lambda d: (current_date - datetime.strptime(d, "%Y-%m-%d")).days
                        if d else 0,
                        return_dtype=pl.Int64
                    ).alias('holding_days')
                ])

                # 执行卖出并创建交易记录
                total_net_revenue = sellable.select(pl.col('net_revenue').sum()).item()
                new_cash += total_net_revenue

                for row in sellable.iter_rows(named=True):
                    code = row['code']
                    del new_portfolio[code]
                    if code in position_info:
                        del position_info[code]

                    position_id = f"{row['entry_date']}-{code}"

                    trades.append(TradeRecord(
                        date=date_str,
                        code=code,
                        action="sell",
                        shares=int(row['shares']),
                        price=row['filled_price'],
                        amount=row['net_revenue'],
                        commission=row['commission'],
                        tax=row['tax'],
                        profit_loss=row['profit_loss'],
                        roi=row['roi'],
                        entry_price=row['cost'],
                        entry_date=row['entry_date'],
                        exit_price=row['filled_price'],
                        exit_date=date_str,
                        holding_days=int(row['holding_days']),
                        position_id=position_id,
                        indicators=row.get('indicators', {})
                    ))

        # =========================================================================
        # Step 5: 向量化处理买入信号
        # =========================================================================
        buy_signals = signals_df.filter(pl.col('action') == 'buy')

        if not buy_signals.is_empty():
            # 检查持仓限制
            current_positions_count = len(new_portfolio)
            max_positions = self.config.max_positions

            if max_positions is not None:
                if current_positions_count >= max_positions:
                    buy_signals = buy_signals.head(0)
                else:
                    can_buy = max_positions - current_positions_count
                    buy_signals = buy_signals.head(can_buy)

            # 检查单日买入限制
            max_stocks_per_day = self.config.max_stocks_per_day
            if max_stocks_per_day is not None:
                buy_signals = buy_signals.head(max_stocks_per_day)

            # 过滤已持仓股票
            if not positions_df.is_empty():
                existing_codes = set(positions_df['code'].to_list())
                buy_signals = buy_signals.filter(
                    ~pl.col('code').is_in(existing_codes)
                )

            # 关联市场数据
            market_cols = ['code', 'close', 'open', 'is_suspended', 'is_limit_up']
            if self.config.exclude_st:
                market_cols.append('is_st')
            if self.config.volume_cap_ratio > 0:
                market_cols.append('volume')
            buyable = buy_signals.join(
                market_df.select(market_cols),
                on='code', how='inner'
            )

            # 统计被拒绝原因（在主过滤之前）
            try:
                self._rejected_stats.suspended += int(
                    buyable.filter(pl.col('is_suspended') == True).height
                )
                self._rejected_stats.limit_up += int(
                    buyable.filter(pl.col('is_limit_up') == True).height
                )
                if self.config.exclude_st and 'is_st' in buyable.columns:
                    self._rejected_stats.st += int(
                        buyable.filter(pl.col('is_st') == True).height
                    )
            except Exception:
                pass

            # 主体可买过滤
            buy_filter_expr = (
                ((pl.col('close') > 0) | (pl.col('open') > 0)) &
                (pl.col('is_suspended') == False) &
                (pl.col('is_limit_up') == False)
            )
            if self.config.exclude_st and 'is_st' in buyable.columns:
                buy_filter_expr = buy_filter_expr & (pl.col('is_st') == False)
            buyable = buyable.filter(buy_filter_expr)

            if not buyable.is_empty():
                # 向量化计算买入参数 - 使用 close 价格（如果 open 为 0）
                target_investment = new_cash * self.config.position_ratio

                # 应用滑点：买入按 (1 + slippage_rate) 加价
                slippage = self.config.slippage_rate

                buyable = buyable.with_columns([
                    pl.when(pl.col('open') > 0)
                    .then(pl.col('open'))
                    .otherwise(pl.col('close'))
                    .alias('trade_price'),
                ]).with_columns([
                    (pl.col('trade_price') * (1.0 + slippage)).alias('filled_price'),
                ])

                # 成交量约束：单笔买入股数 <= 当日成交量 × volume_cap_ratio
                if self.config.volume_cap_ratio > 0 and 'volume' in buyable.columns:
                    buyable = buyable.with_columns([
                        ((pl.col('volume') * self.config.volume_cap_ratio).floor().cast(pl.Int64) // 100 * 100).alias('volume_cap_shares'),
                    ])
                    # 当 volume_cap_shares < 100 视为被成交量限制
                    try:
                        self._rejected_stats.volume += int(
                            buyable.filter(
                                (pl.col('volume') > 0) & (pl.col('volume_cap_shares') < 100)
                            ).height
                        )
                    except Exception:
                        pass
                    buyable = buyable.filter(
                        (pl.col('volume') <= 0) | (pl.col('volume_cap_shares') >= 100)
                    )

                buyable = buyable.with_columns([
                    (target_investment / (pl.col('filled_price') * (1 + self.config.commission_rate)))
                    .floor().alias('raw_shares'),
                ]).with_columns([
                    ((pl.col('raw_shares') // 100) * 100).alias('shares'),
                ])

                # 成交量上限钳制
                if self.config.volume_cap_ratio > 0 and 'volume_cap_shares' in buyable.columns:
                    buyable = buyable.with_columns([
                        pl.min_horizontal([pl.col('shares'), pl.col('volume_cap_shares')]).alias('shares'),
                    ])

                # 资金不足统计（在过滤之前）
                try:
                    self._rejected_stats.insufficient_cash += int(
                        buyable.filter(pl.col('shares') < 100).height
                    )
                except Exception:
                    pass

                buyable = buyable.filter(
                    (pl.col('shares') >= 100) &
                    (pl.col('shares') * pl.col('filled_price') <= new_cash)
                )

                if not buyable.is_empty():
                    buyable = buyable.with_columns([
                        (pl.col('shares') * pl.col('filled_price')).alias('cost'),
                    ]).with_columns([
                        pl.max_horizontal([
                            pl.col('cost') * self.config.commission_rate,
                            self.config.min_commission
                        ]).alias('commission'),
                    ]).with_columns([
                        (pl.col('cost') + pl.col('commission')).alias('total_outlay'),
                    ])

                    # 累计滑点成本
                    try:
                        slippage_sum = (buyable['trade_price'] * slippage * buyable['shares']).sum()
                        self._slippage_cost_total += float(slippage_sum)
                    except Exception:
                        pass

                    # 按可用资金排序，选择可负担的交易
                    buyable = buyable.sort('total_outlay')

                    for row in buyable.iter_rows(named=True):
                        total_outlay = row['total_outlay']
                        if total_outlay > new_cash:
                            continue

                        code = row['code']
                        shares = int(row['shares'])

                        position_id = f"{date_str}-{code}"

                        new_portfolio[code] = shares
                        new_cash -= total_outlay

                        position_info[code] = {
                            'cost': total_outlay / shares,
                            'entry_date': date_str,
                            'position_id': position_id
                        }

                        trades.append(TradeRecord(
                            date=date_str,
                            code=code,
                            action="buy",
                            shares=shares,
                            price=row['filled_price'],
                            amount=total_outlay,
                            commission=row['commission'],
                            holding_days=0,
                            position_id=position_id,
                            indicators=row.get('indicators', {})
                        ))

        return new_portfolio, new_cash, trades
    
    def _process_dividends(
        self,
        current_time: pd.Timestamp,
        portfolio: Dict[str, int],
        prev_day_data: Dict[str, Dict[str, Any]],
        current_day_data: Dict[str, Dict[str, Any]],
        cash: float
    ) -> Tuple[float, List[Dict]]:
        """
        处理分红和送转股 - 向量化优化版本
        
        动态复权核心逻辑：
        1. 现金分红：增加账户现金
        2. 送转股：更新持仓数量和成本价
        
        性能优化：
        1. 使用 NumPy 批量计算复权因子变化
        2. 向量化计算分红金额
        3. 减少循环次数
        """
        if not portfolio or not prev_day_data:
            return cash, []
        
        dividends = []
        date_str = current_time.strftime("%Y-%m-%d")
        
        # =========================================================================
        # [向量化优化] 批量处理分红
        # =========================================================================
        codes = list(portfolio.keys())
        shares_arr = np.array([portfolio[c] for c in codes], dtype=np.float64)
        
        # 提取数据
        prev_factors = np.array([
            float(prev_day_data.get(c, {}).get('adj_factor', 1.0)) for c in codes
        ])
        curr_factors = np.array([
            float(current_day_data.get(c, {}).get('adj_factor', 1.0)) for c in codes
        ])
        prev_closes = np.array([
            float(prev_day_data.get(c, {}).get('close', 0)) for c in codes
        ])
        prev_mvs = np.array([
            float(prev_day_data.get(c, {}).get('total_mv', 0)) for c in codes
        ])
        curr_mvs = np.array([
            float(current_day_data.get(c, {}).get('total_mv', 0)) for c in codes
        ])
        curr_closes = np.array([
            float(current_day_data.get(c, {}).get('close', 0)) for c in codes
        ])
        
        # 计算复权因子变化
        factor_change_mask = np.abs(curr_factors - prev_factors) > 1e-6
        
        if not np.any(factor_change_mask):
            return cash, []
        
        # 计算股本变化比例
        with np.errstate(divide='ignore', invalid='ignore'):
            prev_shares_total = np.where(prev_closes > 0, prev_mvs / prev_closes, 0)
            curr_shares_total = np.where(curr_closes > 0, curr_mvs / curr_closes, 0)
            shares_change_ratio = np.where(
                prev_shares_total > 0,
                np.abs(curr_shares_total / prev_shares_total - 1),
                0
            )
        
        # 现金分红条件：股本变化比例 < 5%
        cash_dividend_mask = factor_change_mask & (shares_change_ratio < 0.05)
        
        # 计算每股分红金额
        with np.errstate(divide='ignore', invalid='ignore'):
            dividend_per_share = prev_closes * (1 - prev_factors / curr_factors)
        
        dividend_per_share = np.where(dividend_per_share > 0, dividend_per_share, 0)
        total_dividends = shares_arr * dividend_per_share * cash_dividend_mask
        
        # 累加现金分红
        cash += float(np.sum(total_dividends))
        
        # 记录现金分红
        for i, code in enumerate(codes):
            if cash_dividend_mask[i] and total_dividends[i] > 0:
                dividends.append({
                    "date": date_str,
                    "code": code,
                    "type": "cash",
                    "dividend": float(total_dividends[i]),
                    "dividend_per_share": float(dividend_per_share[i])
                })
        
        # 送转/拆股条件：股本变化比例 >= 5%
        split_mask = factor_change_mask & (shares_change_ratio >= 0.05)
        
        for i, code in enumerate(codes):
            if split_mask[i]:
                old_shares = int(shares_arr[i])
                # 持仓数量按复权因子比例调整
                adj_ratio = curr_factors[i] / prev_factors[i]
                new_shares = int(round(old_shares * adj_ratio))
                
                if new_shares != old_shares and new_shares > 0:
                    # 更新持仓数量
                    portfolio[code] = new_shares
                    
                    # 更新持仓成本价（按比例调整）
                    if code in self._position_info:
                        old_cost = self._position_info[code].get('cost', 0)
                        if old_cost > 0:
                            self._position_info[code]['cost'] = old_cost / adj_ratio
                    
                    dividends.append({
                        "date": date_str,
                        "code": code,
                        "type": "split",
                        "old_shares": old_shares,
                        "new_shares": new_shares,
                        "adj_ratio": adj_ratio
                    })
        
        return cash, dividends
    
    def _calculate_portfolio_value(
        self,
        positions: Dict[str, int],
        data_dict: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        计算持仓市值 - 向量化优化版本
        
        性能优化：
        1. 使用 NumPy 向量化计算市值
        2. 避免逐股票循环累加
        """
        if not positions or not data_dict:
            return 0.0
        
        # =========================================================================
        # [向量化优化] 使用 NumPy 批量计算市值
        # =========================================================================
        codes = list(positions.keys())
        shares = np.array([positions[c] for c in codes], dtype=np.float64)
        
        prices = np.array([
            float(data_dict.get(c, {}).get('close', 0)) 
            for c in codes
        ], dtype=np.float64)
        
        return float(np.dot(shares, prices))
    
    def _should_record_equity(self, idx: int) -> bool:
        """判断是否应该记录权益曲线"""
        if self.config.time_granularity == TimeGranularity.DAILY:
            return True
        return idx % 60 == 0  # 分钟级别每60分钟记录一次
    
    def _log_trade(self, trade: TradeRecord):
        """记录交易日志"""
        action_cn = "买入" if trade.action == 'buy' else "卖出"
        logger.info(f"[TRADE] {trade.date} {action_cn} {trade.code}: {trade.shares}股 @ {trade.price:.2f}")
        if trade.action == 'sell':
            logger.info(f"   PnL: {trade.profit_loss:,.2f} (ROI: {trade.roi:.2f}%)")
    
    def _format_trade_event(self, trade: TradeRecord) -> Dict[str, Any]:
        """
        格式化交易事件，对齐前端 API 字段命名
        
        字段映射：
        - shares → quantity
        - profit_loss → profitLoss
        - entry_price → entryPrice
        - entry_date → entryDate
        - exit_price → exitPrice
        - exit_date → exitDate
        - holding_days → holdingDays
        - position_id → positionId
        """
        stock_code = str(trade.code).zfill(6) if trade.code.isdigit() else trade.code
        position_id = trade.position_id or f"{trade.entry_date}-{trade.code}"
        
        return {
            "type": "new_trade_engine",
            "data": {
                "id": f"{trade.date}-{stock_code}-{trade.action}",
                "date": trade.date,
                "symbolCode": stock_code,
                "symbol": stock_code,
                "code": stock_code,
                "action": trade.action,
                "price": trade.price,
                "quantity": trade.shares,
                "shares": trade.shares,
                "amount": trade.amount,
                "commission": trade.commission,
                "tax": trade.tax,
                "profitLoss": trade.profit_loss,
                "profit_loss": trade.profit_loss,
                "roi": trade.roi,
                "entryPrice": trade.entry_price,
                "entry_price": trade.entry_price,
                "entryDate": trade.entry_date,
                "entry_date": trade.entry_date,
                "exitPrice": trade.exit_price if trade.action == 'sell' else 0.0,
                "exit_price": trade.exit_price if trade.action == 'sell' else 0.0,
                "exitDate": trade.exit_date if trade.action == 'sell' else "",
                "exit_date": trade.exit_date if trade.action == 'sell' else "",
                "holdingDays": trade.holding_days,
                "holding_days": trade.holding_days,
                "positionId": position_id,
                "position_id": position_id,
                "indicators": trade.indicators
            }
        }
    
    def _log_performance_if_slow(
        self,
        idx: int,
        total_steps: int,
        current_time: pd.Timestamp,
        perf_breakdown: Dict[str, float]
    ):
        """如果性能较慢则记录日志"""
        PERF_THRESHOLD_MS = 200
        is_slow = perf_breakdown.get('total', 0) > PERF_THRESHOLD_MS
        is_first = idx == 1
        is_last = idx == total_steps
        
        if is_first or is_last or is_slow:
            log_level = logger.warning if (is_slow or is_first) else logger.info
            log_msg = (
                f"[PERF][Day {idx}] {current_time.strftime('%Y-%m-%d')}: "
                f"总耗时={perf_breakdown.get('total', 0):.1f}ms | "
                f"数据加载={perf_breakdown.get('data_load', 0):.1f}ms | "
                f"信号生成={perf_breakdown.get('signal_generation', 0):.1f}ms | "
                f"交易执行={perf_breakdown.get('execute_trades', 0):.1f}ms"
            )
            if is_slow and not is_first:
                log_msg += " [SLOW]"
            log_level(log_msg)
    
    def _save_performance_report(
        self,
        perf_snapshots: List[Dict],
        strategy: Any
    ):
        """保存性能报告"""
        try:
            run_id = int(time.time())
            perf_report_file = Path(Config.DB_PATH).parent / f"perf_report_{run_id}.json"
            
            strategy_name = getattr(strategy, 'strategy_name', 
                         getattr(strategy, 'name', 'Unknown'))
            
            with open(perf_report_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "strategy": strategy_name,
                    "granularity": self.config.time_granularity.value,
                    "snapshots": perf_snapshots
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[PERF] 性能报告已保存至: {perf_report_file}")
        except Exception as e:
            logger.error(f"[PERF] 保存性能报告失败: {e}")
    
    def _calculate_final_result(
        self,
        all_trades: List[TradeRecord],
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp
    ) -> BacktestResult:
        """
        计算最终回测结果 - 向量化 + Numba 加速版本
        
        性能优化：
        1. 使用 NumPy 向量化计算盈亏统计
        2. 使用 Numba JIT 加速最大回撤、夏普比率等计算
        3. 减少内存分配和循环开销
        """
        # =========================================================================
        # Step 1: 交易统计 - 向量化计算
        # =========================================================================
        sell_trades = [t for t in all_trades if t.action == 'sell']
        trade_count = len(sell_trades)
        
        if trade_count > 0:
            profit_losses = np.array([t.profit_loss for t in sell_trades], dtype=np.float64)
            rois = np.array([t.roi for t in sell_trades], dtype=np.float64)
            
            total_profit = float(np.sum(profit_losses[profit_losses > 0]))
            total_loss = float(np.sum(np.abs(profit_losses[profit_losses < 0])))
            win_trades = int(np.sum(profit_losses > 0))
            
            win_rate = (win_trades / trade_count * 100)
            profit_factor = (total_profit / total_loss) if total_loss > 0 else (total_profit if total_profit > 0 else 0.0)
            avg_trade_return = float(np.mean(rois))
            
            # 使用 Numba 加速计算连胜/连亏
            profit_signs = np.sign(profit_losses).astype(np.float64)
            max_winning_streak, max_losing_streak = _calculate_streaks_numba(profit_signs)
        else:
            total_profit = total_loss = win_rate = profit_factor = avg_trade_return = 0.0
            max_winning_streak = max_losing_streak = 0
        
        # =========================================================================
        # Step 2: 最大回撤 - Numba 加速
        # =========================================================================
        max_drawdown = 0.0
        if self._equity_history:
            equity_values = np.array([v for _, v in self._equity_history], dtype=np.float64)
            max_drawdown = _calculate_drawdown_numba(equity_values)
        
        # =========================================================================
        # Step 3: 收益率计算
        # =========================================================================
        final_equity = self._equity_history[-1][1] if self._equity_history else self.config.initial_capital
        total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital * 100
        
        days = (end_ts - start_ts).days
        years = days / 365.25
        annualized_return = ((final_equity / self.config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else total_return
        
        # =========================================================================
        # Step 4: 风险指标 - Numba 加速
        # =========================================================================
        sharpe_ratio = sortino_ratio = volatility = calmar_ratio = 0.0
        
        if len(self._equity_history) > 1:
            try:
                equity_values = np.array([v for _, v in self._equity_history], dtype=np.float64)
                
                # 向量化计算日收益率
                daily_returns = np.diff(equity_values) / equity_values[:-1]
                daily_returns = daily_returns[~np.isnan(daily_returns) & ~np.isinf(daily_returns)]
                
                if len(daily_returns) > 0:
                    volatility = float(np.std(daily_returns) * np.sqrt(252) * 100)
                    
                    # 使用 Numba 加速夏普比率计算
                    sharpe_ratio = _calculate_sharpe_numba(daily_returns)
                    
                    # 使用 Numba 加速索提诺比率计算
                    sortino_ratio = _calculate_sortino_numba(daily_returns)
                    
                    if max_drawdown != 0:
                        calmar_ratio = float(annualized_return / abs(max_drawdown))
            except Exception as e:
                logger.error(f"计算风险指标失败: {e}")
        
        # =========================================================================
        # Step 5: 生成权益曲线数据
        # =========================================================================
        equity_curve = [{"date": d, "equity": round(v, 2)} for d, v in self._equity_history]

        return BacktestResult(
            final_equity=final_equity,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            volatility=volatility,
            win_rate=win_rate,
            profit_factor=profit_factor,
            trade_count=trade_count,
            avg_trade_return=avg_trade_return,
            max_winning_streak=max_winning_streak,
            max_losing_streak=max_losing_streak,
            calmar_ratio=calmar_ratio,
            equity_curve=equity_curve,
            trades=all_trades,
            rejected_orders=self._rejected_stats.to_dict(),
            slippage_cost=round(self._slippage_cost_total, 2),
            filter_stats={
                "slippageRate": self.config.slippage_rate,
                "excludeSt": self.config.exclude_st,
                "volumeCapRatio": self.config.volume_cap_ratio,
                "minTradeAmount": self.config.min_trade_amount,
            },
        )
    
    def _persist_results(
        self,
        result: BacktestResult,
        all_trades: List[TradeRecord],
        strategy: Any,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp
    ):
        """
        持久化回测结果到 Parquet
        
        性能优化：
        - 使用 Polars 直接写入 Parquet（比 pandas 快 2-3 倍）
        - 异步写入（非阻塞）
        - 精简字段（只保存必要数据）
        """
        try:
            from pathlib import Path
            import uuid
            from datetime import datetime
            
            strategy_name = getattr(strategy, 'strategy_name',
                         getattr(strategy, 'name', 'Unknown'))
            
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
            
            output_dir = Path("./data/backtest_results")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            results_summary = {
                'run_id': [run_id],
                'strategy_name': [strategy_name],
                'start_date': [start_ts.strftime("%Y-%m-%d")],
                'end_date': [end_ts.strftime("%Y-%m-%d")],
                'initial_capital': [self.config.initial_capital],
                'final_capital': [result.final_equity],
                'total_return': [result.total_return],
                'annual_return': [result.annualized_return],
                'max_drawdown': [result.max_drawdown],
                'sharpe_ratio': [result.sharpe_ratio],
                'sortino_ratio': [result.sortino_ratio],
                'win_rate': [result.win_rate],
                'profit_factor': [result.profit_factor],
                'trade_count': [len(all_trades)],
                'created_at': [datetime.now().isoformat()]
            }
            
            results_df = pl.DataFrame(results_summary)
            results_path = output_dir / f"result_{run_id}.parquet"
            results_df.write_parquet(results_path, compression='snappy')
            
            if all_trades:
                trades_data = {
                    'run_id': [run_id] * len(all_trades),
                    'code': [t.code for t in all_trades],
                    'action': [t.action for t in all_trades],
                    'date': [t.date for t in all_trades],
                    'price': [t.price for t in all_trades],
                    'shares': [t.shares for t in all_trades],
                    'amount': [t.amount for t in all_trades],
                    'profit_loss': [t.profit_loss for t in all_trades],
                    'roi': [t.roi for t in all_trades],
                    'holding_days': [t.holding_days for t in all_trades]
                }
                
                trades_df = pl.DataFrame(trades_data)
                trades_path = output_dir / f"trades_{run_id}.parquet"
                trades_df.write_parquet(trades_path, compression='snappy')
            
            logger.info(f"[Parquet] 回测结果已保存 (run_id: {run_id}, 交易数: {len(all_trades)})")
            
        except Exception as e:
            logger.error(f"[Parquet] 数据持久化失败: {e}")


def _trade_to_dict(trade: TradeRecord) -> Dict[str, Any]:
    """转换交易记录为字典"""
    stock_code = str(trade.code).zfill(6) if trade.code.isdigit() else trade.code
    return {
        "id": f"{trade.date}_{stock_code}_{trade.action}",
        "date": trade.date,
        "symbol": stock_code,
        "symbolCode": stock_code,
        "code": stock_code,
        "action": trade.action,
        "price": trade.price,
        "quantity": trade.shares,
        "shares": trade.shares,
        "commission": trade.commission,
        "cost": trade.amount if trade.action == 'buy' else 0,
        "revenue": trade.amount if trade.action == 'sell' else 0,
        "profitLoss": trade.profit_loss,
        "profit_loss": trade.profit_loss,
        "roi": trade.roi,
        "entry_price": trade.entry_price,
        "holdingDays": trade.holding_days
    }
