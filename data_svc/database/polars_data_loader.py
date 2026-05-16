"""
Polars 数据加载器 - 完全跳过 Pandas，直接构建矩阵

核心优化：
1. 使用 Polars 零拷贝读取 Parquet
2. 直接构建 NumPy 矩阵，无需 Pandas DataFrame
3. 内存映射保存，快速加载
"""
import numpy as np
import polars as pl
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class PolarsDataLoader:
    """
    纯 Polars 数据加载器
    
    完全跳过 Pandas，直接从 Parquet 构建 NumPy 矩阵
    """
    
    def __init__(self, parquet_dir: str = "data/parquet_data"):
        self.parquet_dir = Path(parquet_dir)
        
    def load_period_to_matrix(
        self,
        start_date: str,
        end_date: str,
        required_fields: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        加载指定时间段的数据，直接构建矩阵
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            required_fields: 需要的字段列表
            
        Returns:
            包含矩阵数据的字典，或 None 如果加载失败
        """
        t_start = time.perf_counter()
        
        if required_fields is None:
            required_fields = [
                'open', 'high', 'low', 'close', 'volume', 'amount',
                'total_mv', 'turnover_rate', 'volume_ratio',
                'is_st', 'is_kc', 'is_cy'
            ]
        
        try:
            # 1. 使用 Polars 读取 Parquet（零拷贝）
            daily_path = self.parquet_dir / "stock_daily.parquet"
            info_path = self.parquet_dir / "stock_info.parquet"
            limit_path = self.parquet_dir / "stock_limit_status.parquet"
            
            # 读取 stock_daily（使用 filter pushdown）
            t_read_start = time.perf_counter()
            
            # 构建列选择
            base_cols = ['stock_code', 'trade_date']
            select_cols = base_cols + [f for f in required_fields if f not in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']]
            
            # 使用 Polars 的 lazy API 进行高效过滤
            lf_daily = pl.scan_parquet(daily_path)
            
            # 过滤日期范围
            lf_daily = lf_daily.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date) &
                (pl.col('volume') > 0) &
                (pl.col('close').is_not_null())
            )
            
            # 选择列
            lf_daily = lf_daily.select(select_cols)
            
            # 收集结果
            df_daily = lf_daily.collect()
            
            t_read_end = time.perf_counter()
            logger.info(f"[PolarsLoader] 读取 stock_daily: {(t_read_end - t_read_start)*1000:.1f}ms, 行数: {len(df_daily)}")
            
            if df_daily.is_empty():
                logger.warning(f"[PolarsLoader] 无数据: {start_date} 到 {end_date}")
                return None
            
            # 2. 读取 stock_info（小表，全量读取）
            t_info_start = time.perf_counter()
            df_info = pl.read_parquet(info_path)
            df_info = df_info.select(['stock_code', 'is_kc', 'is_cy', 'is_st', 'list_date'])
            t_info_end = time.perf_counter()
            logger.info(f"[PolarsLoader] 读取 stock_info: {(t_info_end - t_info_start)*1000:.1f}ms")
            
            # 3. 读取 limit_status（日期范围过滤）
            t_limit_start = time.perf_counter()
            lf_limit = pl.scan_parquet(limit_path)
            lf_limit = lf_limit.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date)
            )
            lf_limit = lf_limit.select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
            df_limit = lf_limit.collect()
            t_limit_end = time.perf_counter()
            logger.info(f"[PolarsLoader] 读取 limit_status: {(t_limit_end - t_limit_start)*1000:.1f}ms")
            
            # 4. 使用 Polars 进行 Join（极速）
            t_join_start = time.perf_counter()
            
            # Join stock_info
            df_result = df_daily.join(df_info, on='stock_code', how='left')
            
            # Join limit_status
            if not df_limit.is_empty():
                df_result = df_result.join(df_limit, on=['stock_code', 'trade_date'], how='left')
            
            # 填充缺失值
            fill_cols = ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']
            for col in fill_cols:
                if col in df_result.columns:
                    df_result = df_result.with_columns(pl.col(col).fill_null(0))
                else:
                    df_result = df_result.with_columns(pl.lit(0).alias(col))
            
            t_join_end = time.perf_counter()
            logger.info(f"[PolarsLoader] Join 和填充: {(t_join_end - t_join_start)*1000:.1f}ms")
            
            # 5. 直接构建矩阵（无需转换为 Pandas）
            t_matrix_start = time.perf_counter()
            
            # 获取唯一的日期和股票代码
            trading_dates = df_result['trade_date'].unique().sort().to_list()
            stock_codes = df_result['stock_code'].unique().sort().to_list()
            
            T = len(trading_dates)
            N = len(stock_codes)
            
            # 创建映射
            date_to_idx = {d: i for i, d in enumerate(trading_dates)}
            code_to_idx = {c: i for i, c in enumerate(stock_codes)}
            
            # 添加索引列 - 使用 replace 代替 map_dict
            df_result = df_result.with_columns([
                pl.col('trade_date').replace(date_to_idx).alias('date_idx'),
                pl.col('stock_code').replace(code_to_idx).alias('code_idx')
            ])
            
            # 初始化矩阵
            all_fields = required_fields + ['is_limit_up', 'is_limit_down', 'is_suspended']
            matrices = {}
            
            for field in all_fields:
                if field in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']:
                    matrices[field] = np.full((T, N), 0, dtype=np.int8)
                else:
                    matrices[field] = np.full((T, N), np.nan, dtype=np.float32)
            
            # 转换为 NumPy 进行批量填充
            df_pandas = df_result.to_pandas()
            
            t_indices = df_pandas['date_idx'].values.astype(int)
            n_indices = df_pandas['code_idx'].values.astype(int)
            
            for field in all_fields:
                if field in df_pandas.columns:
                    vals = df_pandas[field].values
                    mask = pd.notna(vals)
                    if mask.any():
                        matrices[field][t_indices[mask], n_indices[mask]] = vals[mask]
            
            t_matrix_end = time.perf_counter()
            logger.info(f"[PolarsLoader] 构建矩阵: {(t_matrix_end - t_matrix_start)*1000:.1f}ms")
            
            t_total = time.perf_counter() - t_start
            logger.info(f"[PolarsLoader] 总计: {t_total*1000:.1f}ms, T={T}, N={N}")
            
            return {
                'matrices': matrices,
                'trading_dates': trading_dates,
                'stock_codes': stock_codes,
                'T': T,
                'N': N
            }
            
        except Exception as e:
            logger.error(f"[PolarsLoader] 加载失败: {e}", exc_info=True)
            return None


# 全局实例
_polars_loader: Optional[PolarsDataLoader] = None

def get_polars_loader(parquet_dir: str = "data/parquet_data") -> PolarsDataLoader:
    """获取全局 Polars 数据加载器实例"""
    global _polars_loader
    if _polars_loader is None:
        _polars_loader = PolarsDataLoader(parquet_dir)
    return _polars_loader
