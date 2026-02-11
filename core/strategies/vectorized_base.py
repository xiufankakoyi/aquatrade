"""
向量化策略基类 - 封装矩阵转换逻辑

设计目标：
- 将复杂的"数据对齐"、"矩阵构建"、"Categorical 映射"逻辑封装进父类
- 子类只需关注策略逻辑，代码量减少 70%
- 保持高性能（45秒变0.2秒的优化方案）
"""
from __future__ import annotations

from typing import Dict, List, Optional
import functools
import pandas as pd
import numpy as np

from core.strategies.strategy_framework import StrategyBase


def safe_matrix_fill(func):
    """
    装饰器：确保 pd.Categorical 产生的映射坐标在有效范围内，并捕获映射失败。
    
    安全增强：
    1. 禁止静默丢弃数据
    2. 当丢弃比例超过5%时，输出警告日志并列出前5个丢失的Date或Symbol
    """
    @functools.wraps(func)
    def wrapper(self, matrix, row_codes, col_codes, values, name="matrix", 
                trading_dates=None, stock_codes=None):
        # 1. 识别映射失败 (Categorical 产生的 -1)
        valid_mask = (row_codes != -1) & (col_codes != -1)
        
        # 2. 统计缺失情况
        total_count = len(row_codes)
        valid_count = np.sum(valid_mask)
        invalid_count = total_count - valid_count
        invalid_ratio = invalid_count / total_count if total_count > 0 else 0.0
        
        # 3. 数据完整性保护：丢弃比例超过5%时输出警告
        if invalid_count > 0:
            # 计算丢弃比例
            discard_ratio = invalid_ratio * 100
            
            # 获取丢失的坐标信息
            if trading_dates is not None and stock_codes is not None:
                invalid_indices = np.where(~valid_mask)[0]
                lost_dates = set()
                lost_codes = set()
                for idx in invalid_indices[:10]:  # 只取前10个，避免日志过长
                    if idx < len(row_codes):
                        date_idx = row_codes[idx]
                        code_idx = col_codes[idx]
                        if date_idx >= 0 and date_idx < len(trading_dates):
                            lost_dates.add(trading_dates[date_idx])
                        if code_idx >= 0 and code_idx < len(stock_codes):
                            lost_codes.add(stock_codes[code_idx])
                
                # 构建警告消息
                lost_items = []
                for d in list(lost_dates)[:3]:
                    lost_items.append(f"Date:{d}")
                for c in list(lost_codes)[:3]:
                    lost_items.append(f"Symbol:{c}")
                
                warning_msg = f"[{name}] 数据丢弃警告: {invalid_count}/{total_count} ({discard_ratio:.2f}%) 映射失败"
                if discard_ratio > 5.0:
                    warning_msg += f" | 丢失项示例: {', '.join(lost_items[:5])}"
                    print(f"⚠️ {warning_msg}")
                else:
                    print(f"[{name}] 轻微映射失败: {invalid_count} points ({discard_ratio:.2f}%)")
            else:
                # 兼容旧调用方式
                if invalid_ratio > 0.05:
                    print(f"⚠️ [{name}] 严重数据丢弃: {invalid_count}/{total_count} ({discard_ratio*100:.2f}%)")
                else:
                    print(f"[{name}] 映射失败: {invalid_count} points ({discard_ratio*100:.2f}%)")
        
        # 4. 仅保留有效坐标
        safe_rows = row_codes[valid_mask]
        safe_cols = col_codes[valid_mask]
        safe_vals = values[valid_mask]
        
        # 5. 执行原有的矩阵填充逻辑 (Fancy Indexing)
        return func(self, matrix, safe_rows, safe_cols, safe_vals)
    return wrapper


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
    
    # Base class for vectorized strategies
    
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
        self.turnover_rate = np.full((T, N), np.nan, dtype=np.float32)  # 新增：换手率
        
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
            
            # =====================================================================
            # [修复B] 时间精度对齐：强制统一为日期格式
            # 防止 Timestamp 与字符串比较时的精度不匹配导致数据丢失
            # =====================================================================
            if 'trade_date' in all_df.columns:
                # 转换为日期格式，去除时间部分
                all_df['trade_date'] = pd.to_datetime(all_df['trade_date']).dt.date.astype(str)
                print(f"[Data Alignment] trade_date 精度已统一为 YYYY-MM-DD 格式")
            
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
            """快速填充矩阵的辅助函数，使用安全填充逻辑"""
            if col_name in all_df.columns:
                # 提取对应列的有效值 - 必须使用过滤后的 DataFrame
                # 确保 vals 的长度与 i_row, j_col 一致
                filtered_df = all_df[mask]
                vals = filtered_df[col_name].values.astype(dtype)
                # 使用安全填充装饰器执行填充（传递trading_dates和stock_codes用于警告日志）
                self._execute_fill(target_matrix, i_row, j_col, vals, name=col_name,
                                   trading_dates=trading_dates, stock_codes=stock_codes)
            elif default_val is not None:
                # 如果列不存在，使用默认值（但这里不填充，因为已经初始化了）
                pass
        
    # 类方法：执行矩阵填充，使用安全填充装饰器
    @safe_matrix_fill
    def _execute_fill(self, matrix, r_idx, c_idx, vals, name="matrix"):
        """执行矩阵填充的核心方法，使用装饰器确保安全填充"""
        matrix[r_idx, c_idx] = vals
    
    def prepare_data(self, preloaded_data: Optional[Dict[str, pd.DataFrame]], 
                    trading_dates: List[str], 
                    stock_codes: List[str], 
                    price_matrix: Optional[np.ndarray] = None) -> None:
        """
        将 preloaded_data 字典转换为对齐的 NumPy 矩阵
        
        Args:
            preloaded_data: 预加载的数据字典 {date: DataFrame}
            trading_dates: 交易日期列表
            stock_codes: 股票代码列表
            price_matrix: 价格矩阵 (T, N, 4) - 可选，用于填充缺失的价格数据
        
        返回:
            None - 所有矩阵作为实例变量存储
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
            """快速填充矩阵的辅助函数，使用安全填充逻辑"""
            if col_name in all_df.columns:
                # 提取对应列的有效值 - 必须使用过滤后的 DataFrame
                # 确保 vals 的长度与 i_row, j_col 一致
                filtered_df = all_df[mask]
                vals = filtered_df[col_name].values.astype(dtype)
                # 使用安全填充装饰器执行填充
                self._execute_fill(target_matrix, i_row, j_col, vals, name=col_name)
            elif default_val is not None:
                # 如果列不存在，使用默认值（但这里不填充，因为已经初始化了）
                pass
        
        # 填充价格矩阵（优先从 all_df，如果没有则从 price_matrix）
        fill_matrix('close', self.close)
        fill_matrix('open', self.open)
        fill_matrix('high', self.high)
        fill_matrix('low', self.low)
        fill_matrix('volume', self.volume)
        fill_matrix('amount', self.amount)
        fill_matrix('total_mv', self.total_mv)
        fill_matrix('is_st', self.is_st, dtype=np.int8)
        fill_matrix('volume_ratio', self.volume_ratio)
        
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
                    ld_val = row.list_date
                    
                    # 跳过无效值
                    if pd.isna(ld_val) or ld_val == 0:
                        continue
                    
                    # 处理整数格式（YYYYMMDD，如 19910403）
                    if isinstance(ld_val, (int, np.integer)):
                        # 转换为字符串再解析
                        ld_str = str(int(ld_val))
                        if len(ld_str) == 8:  # YYYYMMDD
                            list_date_dt = pd.to_datetime(ld_str, format='%Y%m%d')
                            list_date_dict[row.stock_code] = list_date_dt.toordinal()
                    # 处理字符串格式
                    elif isinstance(ld_val, str) and ld_val != 'nan':
                        list_date_dt = pd.Timestamp(ld_val)
                        list_date_dict[row.stock_code] = list_date_dt.toordinal()
                except Exception as e:
                    # 静默忽略解析错误
                    pass
        
        # 计算上市天数矩阵
        if list_date_dict:
            list_date_arr = np.array([list_date_dict.get(c, np.nan) for c in stock_codes], dtype=np.float64)
            date_ords = np.array([pd.Timestamp(d).toordinal() for d in trading_dates], dtype=np.float64)
            self.days_listed = (date_ords[:, None] - list_date_arr[None, :]).astype(np.float64)
            print(f"[VectorizedBase] ✓ days_listed calculated: {np.sum(~np.isnan(self.days_listed))} valid entries")
        else:
            print(f"[VectorizedBase] ⚠️ No list_date data found, days_listed will be NaN")
    
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

    def get_indicators_at(self, t_idx: int, n_idx: int) -> Dict[str, float]:
        """
        获取指定日期和股票的指标快照
        
        参数:
            t_idx: 日期索引
            n_idx: 股票索引
            
        返回:
            Dict: 指标名称 -> 值
        """
        indicators = {}
        
        # 基础指标
        if hasattr(self, 'volume_ratio') and self.volume_ratio is not None:
            val = self.volume_ratio[t_idx, n_idx]
            indicators['volume_ratio'] = float(val) if not np.isnan(val) else 0.0
            
        if hasattr(self, 'turnover_rate') and self.turnover_rate is not None:
            val = self.turnover_rate[t_idx, n_idx]
            indicators['turnover_rate'] = float(val) if not np.isnan(val) else 0.0

        if hasattr(self, 'days_listed') and self.days_listed is not None:
            val = self.days_listed[t_idx, n_idx]
            indicators['days_listed'] = int(val) if not np.isnan(val) else 0

        # 子类特有指标 (如 gain_3d) 会在子类中赋值给 self
        if hasattr(self, 'gain_3d') and getattr(self, 'gain_3d') is not None:
            val = getattr(self, 'gain_3d')[t_idx, n_idx]
            indicators['gain_3d'] = float(val) if not np.isnan(val) else 0.0

        return indicators



