"""
BaseDataProvider - 数据提供者抽象基类
======================================

【设计模式】Repository Pattern
【目的】为所有数据存储后端提供统一接口

【核心原则】
1. 上层策略引擎只依赖此接口，不感知底层实现
2. 支持多种后端：ArcticDB、Parquet、内存缓存、Mock（测试）
3. 接口语义清晰，与业务无关

【接口分类】
- 读取接口：get_bars, get_stock_pool, get_trading_dates
- 写入接口：save_daily_data, save_factors
- 分析接口：analyze, calculate_indicator
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
import pandas as pd
import polars as pl
import numpy as np
from datetime import datetime


class BaseDataProvider(ABC):
    """
    数据提供者抽象基类
    
    所有数据存储后端（ArcticDB、Parquet、内存等）都必须实现此接口。
    上层策略引擎通过此接口获取数据，完全解耦底层存储细节。
    
    【实现要求】
    1. 所有方法必须处理空数据情况，返回空 DataFrame 而非 None
    2. 日期格式统一为 "YYYY-MM-DD" 字符串
    3. 股票代码格式统一为 "000001.SZ"（Tushare 格式）
    4. 字段命名遵循 Tushare 规范：open, high, low, close, vol, amount
    """
    
    # ==========================================================================
    # 读取接口
    # ==========================================================================
    
    @abstractmethod
    def get_bars(
        self, 
        symbol: str, 
        start: str, 
        end: str, 
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取 K 线数据 - 最核心的数据接口
        
        Args:
            symbol: 股票代码，如 "000001.SZ"
            start: 开始日期，格式 "YYYY-MM-DD"
            end: 结束日期，格式 "YYYY-MM-DD"
            fields: 指定字段列表，None 表示返回所有字段
            
        Returns:
            DataFrame，列至少包含：
            - trade_date: 交易日期 (str)
            - open: 开盘价 (float)
            - high: 最高价 (float)
            - low: 最低价 (float)
            - close: 收盘价 (float)
            - vol: 成交量 (float)
            - amount: 成交额 (float)
            
        Example:
            >>> df = provider.get_bars("000001.SZ", "2024-01-01", "2024-12-31")
            >>> print(df.columns)
            Index(['trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount'], dtype='object')
        """
        pass
    
    @abstractmethod
    def get_multiple_bars(
        self,
        symbols: List[str],
        start: str,
        end: str,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        批量获取多只股票 K 线数据
        
        Args:
            symbols: 股票代码列表
            start: 开始日期
            end: 结束日期
            fields: 指定字段列表
            
        Returns:
            DataFrame，包含所有股票的数据，增加 stock_code 列标识
        """
        pass
    
    @abstractmethod
    def get_stock_pool(self, date: str) -> pl.DataFrame:
        """
        获取某交易日的股票池
        
        Args:
            date: 交易日期，格式 "YYYY-MM-DD"
            
        Returns:
            Polars DataFrame，包含该交易日可交易的所有股票
            列至少包含：
            - stock_code: 股票代码
            - stock_name: 股票名称
            - industry: 所属行业（可选）
            - market_cap: 市值（可选）
        """
        pass
    
    @abstractmethod
    def get_trading_dates(
        self, 
        start: Optional[str] = None, 
        end: Optional[str] = None
    ) -> List[str]:
        """
        获取交易日历
        
        Args:
            start: 开始日期，None 表示从最早日期开始
            end: 结束日期，None 表示到最新日期
            
        Returns:
            交易日列表，格式 ["2024-01-02", "2024-01-03", ...]，已排序
        """
        pass
    
    @abstractmethod
    def get_latest_price(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票最新价格
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict 包含：
            - price: 最新收盘价
            - date: 最新交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - volume: 成交量
        """
        pass
    
    # ==========================================================================
    # 写入接口
    # ==========================================================================
    
    @abstractmethod
    def save_daily_data(
        self, 
        df: pd.DataFrame, 
        symbol: Optional[str] = None
    ) -> bool:
        """
        保存日线数据
        
        Args:
            df: 日线数据 DataFrame，必须包含 trade_date 列
            symbol: 股票代码，如果 df 包含多只股票则为 None（按 ts_code 分组）
            
        Returns:
            保存成功返回 True，失败返回 False
            
        Note:
            如果数据已存在，应该执行更新操作（upsert）
        """
        pass
    
    @abstractmethod
    def save_factors(
        self,
        df: pd.DataFrame,
        factor_name: str
    ) -> bool:
        """
        保存因子数据
        
        Args:
            df: 因子数据 DataFrame
            factor_name: 因子名称，如 "momentum", "valuation"
            
        Returns:
            保存成功返回 True
        """
        pass
    
    # ==========================================================================
    # 分析接口
    # ==========================================================================
    
    @abstractmethod
    def analyze(
        self,
        symbols: List[str],
        start: str,
        end: str,
        sql: str
    ) -> pd.DataFrame:
        """
        执行分析查询
        
        这是两层架构的核心优势：ArcticDB 存储 + Polars 分析
        
        Args:
            symbols: 股票代码列表
            start: 开始日期
            end: 结束日期
            sql: 查询表达式，表名为 "data"
            
        Returns:
            查询结果 DataFrame
            
        Example:
            >>> result = provider.analyze(["000001.SZ"], "2024-01-01", "2024-12-31", "")
        """
        pass
    
    @abstractmethod
    def calculate_indicator(
        self,
        symbol: str,
        start: str,
        end: str,
        indicator: str,
        params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            symbol: 股票代码
            start: 开始日期
            end: 结束日期
            indicator: 指标名称，如 "ma", "rsi", "macd"
            params: 指标参数，如 {"window": 20} for MA
            
        Returns:
            包含原始数据 + 指标列的 DataFrame
        """
        pass
    
    # ==========================================================================
    # 工具方法（可选实现）
    # ==========================================================================
    
    def get_prev_trade_date(self, date: str) -> Optional[str]:
        """
        获取前一个交易日
        
        默认实现：查询交易日历后返回前一天
        子类可以覆盖以提供更高效的实现
        """
        dates = self.get_trading_dates(end=date)
        if len(dates) < 2:
            return None
        return dates[-2]  # 倒数第二个是前一天
    
    def get_next_trade_date(self, date: str) -> Optional[str]:
        """
        获取后一个交易日
        
        默认实现：查询交易日历后返回后一天
        """
        dates = self.get_trading_dates(start=date)
        if len(dates) < 2:
            return None
        return dates[1]  # 第二个是后一天
    
    def is_trading_day(self, date: str) -> bool:
        """
        判断是否为交易日
        
        默认实现：查询该日是否在交易日历中
        """
        dates = self.get_trading_dates(start=date, end=date)
        return len(dates) > 0
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        获取数据摘要信息
        
        Returns:
            Dict 包含：
            - total_symbols: 股票总数
            - date_range: 数据时间范围
            - total_records: 总记录数（估算）
            - last_update: 最后更新时间
        """
        return {
            "provider_type": self.__class__.__name__,
            "note": "默认实现，子类应覆盖以提供详细信息"
        }
