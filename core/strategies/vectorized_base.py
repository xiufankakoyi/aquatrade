"""
向量化策略基类 - 封装矩阵转换逻辑

设计目标：
- 将复杂的"数据对齐"、"矩阵构建"、"Categorical 映射"逻辑封装进父类
- 子类只需关注策略逻辑，代码量减少 70%
- 保持高性能（45秒变0.2秒的优化方案）
"""
from __future__ import annotations

from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from core.strategies.strategy_framework import StrategyBase


class VectorizedStrategyBase(StrategyBase):
    """
    向量化策略基类
    
    核心功能：
    1. prepare_data() - 将 preloaded_data 字典转换为对齐的 NumPy 矩阵
    2. 自动构建常用矩阵（close, open, volume, total_mv 等）作为实例变量
    3. 处理上市日期转换为天数矩阵
    
    使用方式：
        class MyStrategy(VectorizedStrategyBase):
            def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data):
                # 1. 调用基类准备数据
                self.prepare_data(preloaded_data, trading_dates, stock_codes)
                
                # 2. 使用准备好的矩阵进行策略计算
                buy_signal = (self.total_mv >= min_cap) & (self.volume_ratio > 3)
                ...
    """
    
    strategy_name = "向量化策略基类"
    
    def __init__(self, name: str | None = None):
        super().__init__(name)
        # 矩阵数据（在 prepare_data 中初始化）
        self.close: Optional[np.ndarray] = None
        self.open: Optional[np.ndarray] = None
        self.high: Optional[np.ndarray] = None
        self.low: Optional[np.ndarray] = None
        self.volume: Optional[np.ndarray] = None
        self.amount: Optional[np.ndarray] = None
        self.total_mv: Optional[np.ndarray] = None
        self.is_st: Optional[np.ndarray] = None
        self.volume_ratio: Optional[np.ndarray] = None
        self.days_listed: Optional[np.ndarray] = None
        
        # 维度信息
        self.T: Optional[int] = None  # 时间维度
        self.N: Optional[int] = None   # 股票数量
    
    def prepare_data(
        self,
        preloaded_data: Dict[str, pd.DataFrame],
        trading_dates: List[str],
        stock_codes: List[str],
        price_matrix: Optional[np.ndarray] = None
    ) -> None:
        """
        将 preloaded_data 转换为对齐的 NumPy 矩阵，存储为实例变量
        
        核心优化：使用 pd.Categorical + Fancy Indexing 方案
        性能：45秒 -> 0.2秒
        
        参数:
            preloaded_data: Dict[str, pd.DataFrame] - 预加载的全量数据 {date: df}
            trading_dates: List[str] - 交易日期列表 (T,)
            stock_codes: List[str] - 股票代码列表 (N,)
        
        创建的矩阵（作为实例变量）:
            self.close: (T, N) float32 - 收盘价
            self.open: (T, N) float32 - 开盘价
            self.high: (T, N) float32 - 最高价
            self.low: (T, N) float32 - 最低价
            self.volume: (T, N) float32 - 成交量
            self.amount: (T, N) float32 - 成交额
            self.total_mv: (T, N) float32 - 总市值
            self.is_st: (T, N) int8 - 是否ST (0/1)
            self.volume_ratio: (T, N) float32 - 量比
            self.days_listed: (T, N) float64 - 上市天数
        """
        T = len(trading_dates)
        N = len(stock_codes)
        self.T = T
        self.N = N
        
        # 初始化所有矩阵为 NaN
        self.close = np.full((T, N), np.nan, dtype=np.float32)
        self.open = np.full((T, N), np.nan, dtype=np.float32)
        self.high = np.full((T, N), np.nan, dtype=np.float32)
        self.low = np.full((T, N), np.nan, dtype=np.float32)
        self.volume = np.full((T, N), 0.0, dtype=np.float32)
        self.amount = np.full((T, N), 0.0, dtype=np.float32)
        self.total_mv = np.full((T, N), np.nan, dtype=np.float32)
        self.is_st = np.full((T, N), 0, dtype=np.int8)
        self.volume_ratio = np.full((T, N), np.nan, dtype=np.float32)
        self.days_listed = np.full((T, N), np.nan, dtype=np.float64)
        
        if preloaded_data is None or len(preloaded_data) == 0:
            return
        
        # =====================================================================
        # 步骤1: 合并所有 DataFrame
        # =====================================================================
        try:
            # 过滤掉 None 或空 df
            valid_dfs = [df for df in preloaded_data.values() if df is not None and not df.empty]
            if not valid_dfs:
                return
            
            all_df = pd.concat(valid_dfs, ignore_index=True)
        except Exception as e:
            print(f"[VectorizedStrategyBase] 数据合并失败: {e}")
            return
        
        # =====================================================================
        # 步骤2: 构建坐标索引 (核心优化：Categorical 映射)
        # =====================================================================
        # 将日期和代码转换为 Categorical 类型
        # 这一步会自动将字符串映射为 0..T-1 和 0..N-1 的整数
        all_df['trade_date_cat'] = pd.Categorical(all_df['trade_date'], categories=trading_dates, ordered=True)
        all_df['stock_code_cat'] = pd.Categorical(all_df['stock_code'], categories=stock_codes, ordered=True)
        
        # 获取整数坐标 (int32)
        i_row = all_df['trade_date_cat'].cat.codes.values
        j_col = all_df['stock_code_cat'].cat.codes.values
        
        # 过滤无效数据 (不在回测范围内的日期或股票)
        mask = (i_row >= 0) & (j_col >= 0)
        
        # 提取有效坐标
        i_row = i_row[mask]
        j_col = j_col[mask]
        
        # =====================================================================
        # 步骤3: 填充矩阵 (Fancy Indexing)
        # =====================================================================
        def fill_matrix(col_name: str, target_matrix: np.ndarray, dtype=np.float32, default_val=np.nan):
            """快速填充矩阵的辅助函数"""
            if col_name in all_df.columns:
                # 提取对应列的有效值
                vals = all_df.loc[mask, col_name].values.astype(dtype)
                # 一次性向量化赋值 (Fancy Indexing)
                target_matrix[i_row, j_col] = vals
            elif default_val is not None:
                # 如果列不存在，使用默认值（但这里不填充，因为已经初始化了）
                pass
        
        # 填充价格矩阵（优先从 all_df，如果没有则从 price_matrix）
        fill_matrix('close', self.close)
        fill_matrix('open', self.open)
        fill_matrix('high', self.high)
        fill_matrix('low', self.low)
        
        # 如果价格矩阵未填充且提供了 price_matrix，则从 price_matrix 填充
        if price_matrix is not None:
            if np.all(np.isnan(self.close)):
                self.close = price_matrix[:, :, 3].astype(np.float32)
            if np.all(np.isnan(self.open)):
                self.open = price_matrix[:, :, 0].astype(np.float32)
            if np.all(np.isnan(self.high)):
                self.high = price_matrix[:, :, 1].astype(np.float32)
            if np.all(np.isnan(self.low)):
                self.low = price_matrix[:, :, 2].astype(np.float32)
        
        # 填充其他矩阵
        fill_matrix('volume', self.volume, default_val=0.0)
        fill_matrix('amount', self.amount, default_val=0.0)
        fill_matrix('total_mv', self.total_mv)
        fill_matrix('is_st', self.is_st, dtype=np.int8, default_val=0)
        fill_matrix('volume_ratio', self.volume_ratio)
        
        # =====================================================================
        # 步骤4: 计算上市天数矩阵
        # =====================================================================
        list_date_dict = {}
        if 'list_date' in all_df.columns:
            # 只需要每个 code 对应一个 list_date
            # drop_duplicates 比 groupby 快
            unique_dates = all_df[['stock_code', 'list_date']].drop_duplicates('stock_code')
            # 过滤掉不在 stock_codes 里的
            unique_dates = unique_dates[unique_dates['stock_code'].isin(stock_codes)]
            
            for row in unique_dates.itertuples(index=False):
                try:
                    ld_str = str(row.list_date)
                    if ld_str and ld_str != 'nan':
                        list_date_dict[row.stock_code] = pd.Timestamp(ld_str).toordinal()
                except:
                    pass
        
        # 计算上市天数矩阵
        if list_date_dict:
            list_date_arr = np.array([list_date_dict.get(c, np.nan) for c in stock_codes], dtype=np.float64)
            date_ords = np.array([pd.Timestamp(d).toordinal() for d in trading_dates], dtype=np.float64)
            self.days_listed = (date_ords[:, None] - list_date_arr[None, :]).astype(np.float64)
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,  # (T, N, 4)
        trading_dates: List[str],   # (T,)
        stock_codes: List[str],     # (N,)
        data_query,
        preloaded_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> np.ndarray:
        """
        向量化信号生成（基类实现）
        
        子类应该重写此方法，但可以调用 super().prepare_data() 来准备数据
        
        参数:
            price_matrix: 价格矩阵 (T, N, 4) - [open, high, low, close]
            trading_dates: 交易日期列表 (T,)
            stock_codes: 股票代码列表 (N,)
            data_query: 数据查询对象
            preloaded_data: 预加载的全量数据 Dict[str, pd.DataFrame]
        
        返回:
            signal_matrix: (T, N) int32 - 0=hold, 1=buy, 2=sell
        """
        # 准备数据（子类可以重写此方法，但通常调用 prepare_data 即可）
        self.prepare_data(preloaded_data, trading_dates, stock_codes)
        
        # 如果子类没有重写，返回空信号矩阵
        T, N = len(trading_dates), len(stock_codes)
        return np.zeros((T, N), dtype=np.int32)

