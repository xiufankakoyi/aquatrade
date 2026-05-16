"""
统一数据接口层

整合 LanceDB + Polars 架构，提供简洁的 API。
对外暴露的主要接口，隐藏架构的复杂性。

架构全景:
┌─────────────────────────────────────────────────────────────────────────────┐
│                         统一数据接口层                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     UnifiedDataInterface                            │   │
│  │                                                                     │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────────┐  │   │
│  │  │ LanceDB    │   │ ArrowBridge │   │ PolarsAnalytics         │  │   │
│  │  │ Manager    │-->|             |-->|                         │  │   │
│  │  │ (写入层)    │   │ (交互层)     │   │ (分析层)                 │  │   │
│  │  └─────────────┘   └─────────────┘   └─────────────────────────┘  │   │
│  │                                                                     │   │
│  │  对外 API:                                                          │   │
│  │  - get_stock_data()      # 获取股票数据                             │   │
│  │  - update_data()         # 更新数据                                 │   │
│  │  - run_factor_analysis() # 因子分析                                 │   │
│  │  - run_backtest()        # 回测                                     │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

使用示例:
    >>> from data_svc.unified_data_interface import UnifiedDataInterface
    >>>
    >>> # 初始化接口
    >>> interface = UnifiedDataInterface()
    >>>
    >>> # 获取股票数据 (自动路由)
    >>> df = interface.get_stock_data("000001.SZ", "2024-01-01", "2024-12-31")
    >>>
    >>> # 更新数据
    >>> interface.update_data(start_date="2024-01-01", end_date="2024-12-31")
    >>>
    >>> # 运行回测
    >>> result = interface.run_backtest(strategy=my_strategy)
"""

from typing import Optional, List, Dict, Union, Any, Callable
from datetime import datetime, date
import pandas as pd
import numpy as np
from loguru import logger

from data_svc.storage.lancedb_manager import LanceDBManager, get_lancedb_manager
from data_svc.storage.lancedb_reader import LanceDBDataReader, get_lancedb_reader
from data_svc.bridge import ArrowBridge, get_arrow_bridge
from data_svc.analytics import PolarsAnalytics, get_polars_analytics


class UnifiedDataInterface:
    """
    统一数据接口
    
    这是对外暴露的主要接口，隐藏架构的复杂性:
    
    内部实现:
    ┌─────────────────────────────────────────────────────────────────────┐
    │              UnifiedDataInterface                                   │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐     │
    │  │ LanceDB    │  │ ArrowBridge │  │ PolarsAnalytics         │     │
    │  │ Manager    │->│             │->│                         │     │
    │  │ (写入层)   │  │ (交互层)    │  │ (分析层)                │     │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘     │
    └─────────────────────────────────────────────────────────────────────┘
    
    使用示例:
        >>> interface = UnifiedDataInterface()
        >>>
        >>> # 获取股票数据 (自动路由)
        >>> df = interface.get_stock_data("000001.SZ", "2024-01-01", "2024-12-31")
        >>>
        >>> # 更新数据
        >>> interface.update_data(start_date="2024-01-01", end_date="2024-12-31")
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
        """
        初始化统一数据接口
        
        Args:
            db_path: LanceDB 数据库路径，如果为 None 使用默认配置
        """
        logger.info("[UnifiedDataInterface] 初始化架构...")
        
        self.storage = get_lancedb_manager(db_path)
        logger.info("[UnifiedDataInterface] ✓ 写入层 (LanceDB) 初始化完成")
        
        self.reader = get_lancedb_reader(db_path)
        logger.info("[UnifiedDataInterface] ✓ 读取层 (LanceDB Reader) 初始化完成")
        
        self.bridge = get_arrow_bridge()
        logger.info("[UnifiedDataInterface] ✓ 交互层 (Arrow Bridge) 初始化完成")
        
        self.analytics = get_polars_analytics()
        logger.info("[UnifiedDataInterface] ✓ 分析层 (Polars) 初始化完成")
        
        logger.info("[UnifiedDataInterface] 架构初始化完成")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        规范化股票代码，自动添加正确的交易所后缀
        
        规则:
        - 如果已经包含后缀（如 .SH, .SZ），直接返回
        - 6位数字:
            - 以 600, 601, 603, 605, 688 开头 -> .SH (上海)
            - 以 000, 001, 002, 003 开头 -> .SZ (深圳)
            - 以 300 开头 -> .SZ (创业板)
        - 指数代码映射
        """
        if not symbol or '.' in symbol:
            return symbol
        
        INDEX_MAPPING = {
            '000300': '000300.SH',
            '000905': '000905.SH',
            '000001': '000001.SH',
            '399001': '399001.SZ',
            '000016': '000016.SH',
            '399006': '399006.SZ',
        }
        
        if symbol in INDEX_MAPPING:
            return INDEX_MAPPING[symbol]
        
        if len(symbol) == 6 and symbol.isdigit():
            if symbol.startswith(('600', '601', '603', '605', '688', '689')):
                return f"{symbol}.SH"
            elif symbol.startswith(('000', '001', '002', '003', '300', '301')):
                return f"{symbol}.SZ"
            elif symbol.startswith(('430', '831', '832', '833', '834', '835', '836', '837', '838', '839')):
                return f"{symbol}.BJ"
        
        return symbol
    
    def get_stock_data(
        self,
        symbol: str,
        start: str,
        end: str,
        library: str = "daily",
        as_format: str = "pandas"
    ) -> Union[pd.DataFrame, "pa.Table", "pl.DataFrame"]:
        """
        获取股票数据
        
        工作流程:
        1. 从 LanceDB 读取原始数据 (读取层)
        2. 转换为 Arrow Table (交互层)
        3. 按需返回 Pandas、Arrow 或 Polars 格式
        
        Args:
            symbol: 股票代码 (如 "000001.SZ" 或 "000300")
            start: 开始日期 (YYYY-MM-DD)
            end: 结束日期 (YYYY-MM-DD)
            library: 库名 ("daily", "minute", "tick")
            as_format: 返回格式 ("pandas", "arrow", "polars")

        Returns:
            股票数据，格式由 as_format 参数决定

        Example:
            >>> df = interface.get_stock_data("000001.SZ", "2024-01-01", "2024-12-31")
            >>> print(df.head())
        """
        logger.debug(f"[UnifiedDataInterface] 获取数据: {symbol}, {start} ~ {end}")

        lookup_symbol = self._normalize_symbol(symbol)

        df = self.reader.read(lookup_symbol, start, end)

        if df.is_empty() and '.' not in symbol:
            df = self.reader.read(f"{symbol}.SH", start, end)
            if not df.is_empty():
                lookup_symbol = f"{symbol}.SH"
            else:
                df = self.reader.read(f"{symbol}.SZ", start, end)
                if not df.is_empty():
                    lookup_symbol = f"{symbol}.SZ"

        if df.is_empty():
            logger.warning(f"[UnifiedDataInterface] 无数据: {symbol}")
            return pd.DataFrame() if as_format == "pandas" else df

        if as_format == "pandas":
            return df.to_pandas()
        elif as_format == "arrow":
            return df.to_arrow()
        elif as_format == "polars":
            return df
        else:
            raise ValueError(f"不支持的格式: {as_format}")
    
    def get_multiple_stocks(
        self,
        symbols: List[str],
        start: str,
        end: str,
        library: str = "market_data"
    ) -> pd.DataFrame:
        """
        批量获取多只股票数据
        
        Args:
            symbols: 股票代码列表
            start: 开始日期
            end: 结束日期
            library: 库名
            
        Returns:
            合并后的 DataFrame
        """
        all_data = []
        
        for symbol in symbols:
            df = self.get_stock_data(symbol, start, end, library, "pandas")
            if not df.empty:
                all_data.append(df)
        
        if not all_data:
            return pd.DataFrame()
        
        return pd.concat(all_data, ignore_index=True)
    
    def update_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        library: str = "market_data",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        更新数据到 LanceDB

        Args:
            start_date: 开始日期，如果为 None 则自动确定
            end_date: 结束日期，如果为 None 则到昨天
            library: 目标库名
            progress_callback: 进度回调函数

        Returns:
            更新统计信息
        """
        from data_svc.storage.unified_updater import UnifiedDataUpdater

        logger.info(f"[UnifiedDataInterface] 开始更新数据到 {library}")

        updater = UnifiedDataUpdater(
            progress_callback=progress_callback
        )

        result = updater.run_sync(
            library=library,
            start_date=start_date,
            end_date=end_date
        )

        logger.info(f"[UnifiedDataInterface] 更新完成: {result}")
        return result
    
    def run_factor_analysis(
        self,
        factor_expr: Any,
        arrow_table: Optional["pa.Table"] = None,
        symbols: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> pd.DataFrame:
        """
        运行因子分析
        
        Args:
            factor_expr: Polars 表达式或计算函数
            arrow_table: 可选的 Arrow Table，如果提供则直接使用
            symbols: 股票代码列表 (如果 arrow_table 为 None 则自动获取)
            start: 开始日期
            end: 结束日期
            
        Returns:
            因子分析结果
        """
        if arrow_table is None:
            if symbols is None or start is None or end is None:
                raise ValueError("必须提供 arrow_table 或 (symbols, start, end)")
            
            df = self.get_multiple_stocks(symbols, start, end)
            arrow_table = self.bridge.from_pandas(df)
        
        pl_df = self.analytics.from_arrow(arrow_table)
        
        if callable(factor_expr):
            result = factor_expr(pl_df)
        else:
            result = pl_df.with_columns(factor_expr)
        
        return self.analytics.to_pandas(result)
    
    def calculate_technical_indicators(
        self,
        symbols: List[str],
        start: str,
        end: str,
        indicators: List[str] = ["ma", "rsi", "macd"]
    ) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            symbols: 股票代码列表
            start: 开始日期
            end: 结束日期
            indicators: 指标列表 ("ma", "rsi", "macd")
            
        Returns:
            包含技术指标的 DataFrame
        """
        df = self.get_multiple_stocks(symbols, start, end)
        if df.empty:
            return df
        
        arrow_table = self.bridge.from_pandas(df)
        
        for indicator in indicators:
            if indicator == "ma":
                arrow_table = self.analytics.calculate_ma(arrow_table)
            elif indicator == "rsi":
                arrow_table = self.analytics.calculate_rsi(arrow_table)
            elif indicator == "macd":
                arrow_table = self.analytics.calculate_macd(arrow_table)
        
        return self.bridge.to_pandas(arrow_table)
    
    def run_backtest(
        self,
        strategy_func: Callable,
        start_date: str,
        end_date: str,
        symbols: Optional[List[str]] = None,
        universe: Optional[str] = None,
        initial_capital: float = 1000000.0
    ) -> pd.DataFrame:
        """
        运行回测
        
        Args:
            strategy_func: 策略函数
            start_date: 回测开始日期
            end_date: 回测结束日期
            symbols: 股票代码列表 (可选)
            universe: 股票池名称 (可选，如 "hs300", "zz500")
            initial_capital: 初始资金
            
        Returns:
            回测结果
        """
        if symbols:
            df = self.get_multiple_stocks(symbols, start_date, end_date)
        else:
            raise NotImplementedError("根据 universe 获取股票池尚未实现")
        
        if df.empty:
            logger.error("[UnifiedDataInterface] 回测数据为空")
            return pd.DataFrame()
        
        arrow_table = self.bridge.from_pandas(df)
        
        result = self.analytics.run_backtest_query(
            arrow_table=arrow_table,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        return result
    
    def get_stock_pool(
        self,
        date: str,
        filters: Optional[Dict[str, Any]] = None,
        universe: Optional[str] = None
    ) -> List[str]:
        """
        获取股票池
        
        Args:
            date: 日期
            filters: 过滤条件
            universe: 股票池名称
            
        Returns:
            股票代码列表
        """
        symbols = self.storage.list_symbols("daily")
        
        if not symbols:
            return []
        
        df_list = []
        for symbol in symbols[:100]:
            df = self.get_stock_data(symbol, date, date)
            if not df.empty:
                df_list.append(df)
        
        if not df_list:
            return []
        
        df = pd.concat(df_list, ignore_index=True)
        arrow_table = self.bridge.from_pandas(df)
        
        pool_df = self.analytics.get_stock_pool(arrow_table, date, filters)
        
        return pool_df["stock_code"].tolist() if not pool_df.empty else []
    
    def get_last_update_date(self, library: str = "market_data") -> Optional[str]:
        """
        获取最后更新日期
        
        Args:
            library: 库名
            
        Returns:
            最后更新日期 (YYYY-MM-DD)，如果没有数据则返回 None
        """
        try:
            symbols = self.storage.list_symbols(library)
            if not symbols:
                return None
            
            df = self.storage.read_data(library, symbols[0])
            if df.empty:
                return None
            
            last_date = df.index.max()
            return last_date.strftime("%Y-%m-%d")
            
        except Exception as e:
            logger.error(f"[UnifiedDataInterface] 获取最后更新日期失败: {e}")
            return None
    
    def health_check(self) -> Dict[str, bool]:
        """
        健康检查
        
        Returns:
            各层健康状态
        """
        return {
            "storage": self.storage.health_check(),
            "bridge": True,
            "analytics": True,
        }
    
    def close(self) -> None:
        """关闭所有连接"""
        logger.info("[UnifiedDataInterface] 关闭连接...")
        
        if self.storage:
            self.storage.close()
        
        if self.analytics:
            self.analytics.close()
        
        logger.info("[UnifiedDataInterface] 连接已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


_unified_data_interface: Optional[UnifiedDataInterface] = None


def get_unified_data_interface(
    db_path: Optional[str] = None,
) -> UnifiedDataInterface:
    """
    获取 UnifiedDataInterface 单例实例

    Args:
        db_path: LanceDB 数据库路径

    Returns:
        UnifiedDataInterface 实例
    """
    global _unified_data_interface
    if _unified_data_interface is None:
        _unified_data_interface = UnifiedDataInterface(db_path)
    return _unified_data_interface


def reset_unified_data_interface():
    """重置单例实例 (用于测试)"""
    global _unified_data_interface
    if _unified_data_interface is not None:
        _unified_data_interface.close()
        _unified_data_interface = None
