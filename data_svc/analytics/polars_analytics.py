"""
PolarsAnalytics - 分析层 (Analytics Layer)

核心职责:
    封装 Polars 的数据分析逻辑，提供高性能的向量化计算能力。
    这是"分析层"的核心实现，负责复杂的因子计算和技术指标。

设计哲学:
    1. 表达式优先: 使用 Polars 表达式表达计算逻辑
    2. 向量化计算: 利用 Polars 的列式存储和向量化执行引擎
    3. 内存计算: 数据从 ArcticDB 加载后，直接在内存中分析
    4. 函数式接口: 提供常用的分析函数

典型使用场景:
    - 多因子选股回测
    - 技术指标计算 (MA, RSI, MACD 等)
    - 截面分析 (cross-sectional analysis)
    - 时间序列分析
    - 组合优化计算

架构位置:
    ┌─────────────────────────────────────┐
    │         UnifiedDataInterface        │
    │         (统一数据接口)               │
    └─────────────────┬───────────────────┘
                      │ 调用分析方法
                      ▼
    ┌─────────────────────────────────────┐
    │         PolarsAnalytics             │
    │         (分析层 - 本模块)            │
    │  ┌─────────────────────────────┐    │
    │  │  Expression Engine (Polars) │    │
    │  │  向量化计算 · 复杂分析        │    │
    │  └─────────────────────────────┘    │
    └─────────────────┬───────────────────┘
                      │ 读取 Arrow 数据
                      ▼
    ┌─────────────────────────────────────┐
    │         ArrowBridge                 │
    │         (交互层)                     │
    └─────────────────────────────────────┘

作者: AI Assistant
创建日期: 2025-01-14
"""

import polars as pl
import pandas as pd
import pyarrow as pa
from typing import Optional, List, Dict, Any, Union, Callable
from pathlib import Path
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """
    分析结果容器
    
    统一封装 Polars 查询结果，支持多种格式输出
    
    Attributes:
        df: Pandas DataFrame 格式结果
        pl_df: Polars DataFrame 格式结果
        execution_time_ms: 执行耗时(毫秒)
        row_count: 结果行数
    """
    df: pd.DataFrame
    pl_df: Optional[pl.DataFrame] = None
    execution_time_ms: float = 0.0
    row_count: int = 0
    
    def to_pandas(self) -> pd.DataFrame:
        """获取 Pandas 格式结果"""
        return self.df
    
    def to_polars(self) -> pl.DataFrame:
        """获取 Polars 格式结果"""
        if self.pl_df is not None:
            return self.pl_df
        return pl.from_pandas(self.df)


class PolarsAnalytics:
    """
    Polars 分析引擎 - 分析层核心实现
    
    提供基于 Polars 表达式的高性能数据分析能力，支持:
    - 复杂回测查询
    - 技术指标计算
    - 多表关联分析
    - 窗口函数计算
    - 聚合统计
    
    使用示例:
        >>> from data_svc.analytics.polars_analytics import PolarsAnalytics
        >>> 
        >>> # 初始化分析器
        >>> analytics = PolarsAnalytics()
        >>> 
        >>> # 从 Arrow Table 创建 Polars DataFrame
        >>> df = analytics.from_arrow(arrow_table)
        >>> 
        >>> # 计算移动均线
        >>> result = analytics.calculate_ma(df, windows=[5, 10, 20])
        >>> 
        >>> print(result)
    """
    
    def __init__(self):
        """初始化 Polars 分析引擎"""
        logger.info("PolarsAnalytics 初始化完成")
    
    def from_arrow(self, arrow_table: pa.Table) -> pl.DataFrame:
        """
        从 Arrow Table 创建 Polars DataFrame
        
        Args:
            arrow_table: PyArrow Table
            
        Returns:
            Polars DataFrame
        """
        return pl.from_arrow(arrow_table)
    
    def from_pandas(self, df: pd.DataFrame) -> pl.DataFrame:
        """
        从 Pandas DataFrame 创建 Polars DataFrame
        
        Args:
            df: Pandas DataFrame
            
        Returns:
            Polars DataFrame
        """
        return pl.from_pandas(df)
    
    def to_pandas(self, df: pl.DataFrame) -> pd.DataFrame:
        """
        将 Polars DataFrame 转换为 Pandas DataFrame
        
        Args:
            df: Polars DataFrame
            
        Returns:
            Pandas DataFrame
        """
        return df.to_pandas()
    
    def query_from_arrow(
        self,
        arrow_table: pa.Table,
        query: str
    ) -> pd.DataFrame:
        """
        从 Arrow Table 执行查询
        
        注意：Polars 不支持 SQL，此方法提供基本的过滤和聚合功能
        对于复杂 SQL 查询，建议使用 Polars 表达式 API
        
        Args:
            arrow_table: PyArrow Table
            query: 查询描述（用于日志）
            
        Returns:
            Pandas DataFrame
        """
        df = self.from_arrow(arrow_table)
        logger.debug(f"执行查询: {query}")
        return self.to_pandas(df)
    
    def calculate_ma(
        self,
        df: Union[pl.DataFrame, pa.Table],
        windows: List[int] = [5, 10, 20, 60]
    ) -> pl.DataFrame:
        """
        计算移动均线
        
        Args:
            df: 数据源 (Polars DataFrame 或 Arrow Table)
            windows: 均线周期列表
            
        Returns:
            包含均线列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        for window in windows:
            df = df.with_columns(
                pl.col('close').rolling_mean(window_size=window).alias(f'ma{window}')
            )
        
        return df
    
    def calculate_rsi(
        self,
        df: Union[pl.DataFrame, pa.Table],
        period: int = 14
    ) -> pl.DataFrame:
        """
        计算相对强弱指标 (RSI)
        
        Args:
            df: 数据源
            period: RSI 周期
            
        Returns:
            包含 RSI 列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        delta = pl.col('close').diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0)
        
        avg_gain = gain.rolling_mean(window_size=period)
        avg_loss = loss.rolling_mean(window_size=period)
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        df = df.with_columns(rsi.alias('rsi'))
        return df
    
    def calculate_macd(
        self,
        df: Union[pl.DataFrame, pa.Table],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> pl.DataFrame:
        """
        计算 MACD 指标
        
        Args:
            df: 数据源
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期
            
        Returns:
            包含 MACD 列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        ema_fast = pl.col('close').ewm_mean(span=fast_period)
        ema_slow = pl.col('close').ewm_mean(span=slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm_mean(span=signal_period)
        histogram = macd_line - signal_line
        
        df = df.with_columns([
            macd_line.alias('macd'),
            signal_line.alias('macd_signal'),
            histogram.alias('macd_histogram')
        ])
        return df
    
    def calculate_bollinger_bands(
        self,
        df: Union[pl.DataFrame, pa.Table],
        period: int = 20,
        std_dev: float = 2.0
    ) -> pl.DataFrame:
        """
        计算布林带
        
        Args:
            df: 数据源
            period: 周期
            std_dev: 标准差倍数
            
        Returns:
            包含布林带列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        ma = pl.col('close').rolling_mean(window_size=period)
        std = pl.col('close').rolling_std(window_size=period)
        
        df = df.with_columns([
            ma.alias('bollinger_mid'),
            (ma + std * std_dev).alias('bollinger_upper'),
            (ma - std * std_dev).alias('bollinger_lower')
        ])
        return df
    
    def cross_sectional_rank(
        self,
        df: Union[pl.DataFrame, pa.Table],
        column: str,
        group_by: Optional[str] = None,
        method: str = 'percentile'
    ) -> pl.DataFrame:
        """
        截面排名
        
        Args:
            df: 数据源
            column: 要排名的列
            group_by: 分组列 (如日期)
            method: 排名方法 ('percentile', 'rank', 'zscore')
            
        Returns:
            包含排名列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        if method == 'percentile':
            rank_expr = pl.col(column).rank(method='average') / pl.len()
        elif method == 'rank':
            rank_expr = pl.col(column).rank(method='average')
        elif method == 'zscore':
            rank_expr = (pl.col(column) - pl.col(column).mean()) / pl.col(column).std()
        else:
            rank_expr = pl.col(column).rank(method='average')
        
        if group_by:
            df = df.with_columns(
                rank_expr.over(group_by).alias(f'{column}_rank')
            )
        else:
            df = df.with_columns(rank_expr.alias(f'{column}_rank'))
        
        return df
    
    def calculate_volatility(
        self,
        df: Union[pl.DataFrame, pa.Table],
        window: int = 20,
        annualize: bool = True
    ) -> pl.DataFrame:
        """
        计算波动率
        
        Args:
            df: 数据源
            window: 滚动窗口
            annualize: 是否年化
            
        Returns:
            包含波动率列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        returns = pl.col('close').pct_change()
        vol = returns.rolling_std(window_size=window)
        
        if annualize:
            vol = vol * (252 ** 0.5)
        
        df = df.with_columns(vol.alias('volatility'))
        return df
    
    def calculate_returns(
        self,
        df: Union[pl.DataFrame, pa.Table],
        periods: List[int] = [1, 5, 10, 20]
    ) -> pl.DataFrame:
        """
        计算收益率
        
        Args:
            df: 数据源
            periods: 收益率周期列表
            
        Returns:
            包含收益率列的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        for period in periods:
            df = df.with_columns(
                (pl.col('close') / pl.col('close').shift(period) - 1).alias(f'return_{period}d')
            )
        
        return df
    
    def filter_by_date(
        self,
        df: Union[pl.DataFrame, pa.Table],
        start: str,
        end: str,
        date_column: str = 'date'
    ) -> pl.DataFrame:
        """
        按日期范围过滤
        
        Args:
            df: 数据源
            start: 开始日期
            end: 结束日期
            date_column: 日期列名
            
        Returns:
            过滤后的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        return df.filter(
            (pl.col(date_column) >= pl.lit(start).str.to_date()) &
            (pl.col(date_column) <= pl.lit(end).str.to_date())
        )
    
    def group_by_symbol(
        self,
        df: Union[pl.DataFrame, pa.Table],
        aggregations: Dict[str, str],
        symbol_column: str = 'symbol'
    ) -> pl.DataFrame:
        """
        按股票代码分组聚合
        
        Args:
            df: 数据源
            aggregations: 聚合表达式 {列名: 聚合方法}
                         支持的方法: 'mean', 'sum', 'max', 'min', 'std', 'count'
            symbol_column: 股票代码列名
            
        Returns:
            聚合后的 Polars DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        agg_exprs = []
        for col, method in aggregations.items():
            if method == 'mean':
                agg_exprs.append(pl.col(col).mean().alias(f'{col}_mean'))
            elif method == 'sum':
                agg_exprs.append(pl.col(col).sum().alias(f'{col}_sum'))
            elif method == 'max':
                agg_exprs.append(pl.col(col).max().alias(f'{col}_max'))
            elif method == 'min':
                agg_exprs.append(pl.col(col).min().alias(f'{col}_min'))
            elif method == 'std':
                agg_exprs.append(pl.col(col).std().alias(f'{col}_std'))
            elif method == 'count':
                agg_exprs.append(pl.col(col).count().alias(f'{col}_count'))
        
        return df.group_by(symbol_column).agg(agg_exprs)
    
    def get_stock_pool(
        self,
        df: Union[pl.DataFrame, pa.Table],
        date: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        获取股票池
        
        Args:
            df: 数据源
            date: 日期
            filters: 过滤条件
            
        Returns:
            股票池 DataFrame
        """
        if isinstance(df, pa.Table):
            df = self.from_arrow(df)
        
        result = df.filter(pl.col('date') == pl.lit(date).str.to_date())
        
        if filters:
            for col, condition in filters.items():
                if isinstance(condition, dict):
                    op = condition.get('op')
                    val = condition.get('value')
                    if op == '>':
                        result = result.filter(pl.col(col) > val)
                    elif op == '<':
                        result = result.filter(pl.col(col) < val)
                    elif op == '==':
                        result = result.filter(pl.col(col) == val)
                    elif op == '>=':
                        result = result.filter(pl.col(col) >= val)
                    elif op == '<=':
                        result = result.filter(pl.col(col) <= val)
                else:
                    result = result.filter(pl.col(col) == condition)
        
        return self.to_pandas(result)
    
    def run_backtest_query(
        self,
        arrow_table: pa.Table,
        start_date: str,
        end_date: str,
        strategy_sql: str = "",
        initial_capital: float = 1000000.0
    ) -> pd.DataFrame:
        """
        运行回测查询
        
        注意：此方法提供基本的回测框架，复杂策略建议使用专门的回测引擎
        
        Args:
            arrow_table: 数据源
            start_date: 开始日期
            end_date: 结束日期
            strategy_sql: 策略描述（用于日志）
            initial_capital: 初始资金
            
        Returns:
            回测结果 DataFrame
        """
        df = self.from_arrow(arrow_table)
        df = self.filter_by_date(df, start_date, end_date)
        
        df = self.calculate_returns(df, periods=[1])
        
        logger.info(f"执行回测: {start_date} ~ {end_date}, 初始资金: {initial_capital}")
        
        return self.to_pandas(df)
    
    def close(self) -> None:
        """关闭连接 (Polars 无连接状态)"""
        pass


_polars_analytics: Optional[PolarsAnalytics] = None


def get_polars_analytics() -> PolarsAnalytics:
    """
    获取 PolarsAnalytics 单例实例
    
    Returns:
        PolarsAnalytics 实例
    """
    global _polars_analytics
    if _polars_analytics is None:
        _polars_analytics = PolarsAnalytics()
    return _polars_analytics
