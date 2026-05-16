"""
Polars 数据加载器 V4 - 混合优化策略

核心优化：
1. 大表(stock_daily)使用 scan_parquet + filter pushdown
2. 小表(stock_info, limit_status)使用 read_parquet（更快）
3. 完全跳过 Pandas，纯 Polars 构建矩阵
"""
import numpy as np
import polars as pl
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class PolarsDataLoaderV4:
    """
    混合优化 Polars 数据加载器 V4
    
    大表用 scan_parquet，小表用 read_parquet
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
        加载指定时间段的数据，直接构建矩阵（混合优化版本）
        
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
            daily_path = self.parquet_dir / "stock_daily.parquet"
            info_path = self.parquet_dir / "stock_info.parquet"
            limit_path = self.parquet_dir / "stock_limit_status.parquet"
            
            t_read_start = time.perf_counter()
            
            # 【优化1】大表使用 scan_parquet + filter pushdown
            base_cols = ['stock_code', 'trade_date']
            select_cols = base_cols + [f for f in required_fields if f not in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']]
            
            lf_daily = pl.scan_parquet(daily_path)
            lf_daily = lf_daily.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date) &
                (pl.col('volume') > 0) &
                (pl.col('close').is_not_null())
            )
            lf_daily = lf_daily.select(select_cols)
            df_daily = lf_daily.collect()
            
            # 【优化2】小表使用 read_parquet（更快）
            df_info = pl.read_parquet(info_path)
            df_info = df_info.select(['stock_code', 'is_kc', 'is_cy', 'is_st', 'list_date'])
            
            # 【优化3】limit_status 也用 scan_parquet（中等大小）
            lf_limit = pl.scan_parquet(limit_path)
            lf_limit = lf_limit.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date)
            )
            lf_limit = lf_limit.select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
            df_limit = lf_limit.collect()
            
            t_read_end = time.perf_counter()
            logger.info(f"[PolarsLoaderV4] 读取: {(t_read_end - t_read_start)*1000:.1f}ms, daily={len(df_daily)}, limit={len(df_limit)}")
            
            if df_daily.is_empty():
                logger.warning(f"[PolarsLoaderV4] 无数据: {start_date} 到 {end_date}")
                return None
            
            # 【优化4】使用 Polars 的 join（比 Pandas 快 10-100 倍）
            t_join_start = time.perf_counter()
            
            df_result = df_daily.join(df_info, on='stock_code', how='left')
            
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
            logger.info(f"[PolarsLoaderV4] Join: {(t_join_end - t_join_start)*1000:.1f}ms")
            
            # 5. 直接构建矩阵（纯 Polars，无 Pandas）
            t_matrix_start = time.perf_counter()
            
            trading_dates = df_result['trade_date'].unique().sort().to_list()
            stock_codes = df_result['stock_code'].unique().sort().to_list()
            
            T = len(trading_dates)
            N = len(stock_codes)
            
            date_to_idx = {d: i for i, d in enumerate(trading_dates)}
            code_to_idx = {c: i for i, c in enumerate(stock_codes)}
            
            df_result = df_result.with_columns([
                pl.col('trade_date').replace(date_to_idx).alias('date_idx'),
                pl.col('stock_code').replace(code_to_idx).alias('code_idx')
            ])
            
            all_fields = required_fields + ['is_limit_up', 'is_limit_down', 'is_suspended']
            matrices = {}
            
            for field in all_fields:
                if field in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']:
                    matrices[field] = np.full((T, N), 0, dtype=np.int8)
                else:
                    matrices[field] = np.full((T, N), np.nan, dtype=np.float32)
            
            t_indices = df_result['date_idx'].to_numpy().astype(np.int32)
            n_indices = df_result['code_idx'].to_numpy().astype(np.int32)
            
            for field in all_fields:
                if field in df_result.columns:
                    vals = df_result[field].to_numpy()
                    if vals.dtype == np.float32 or vals.dtype == np.float64:
                        mask = ~np.isnan(vals)
                    else:
                        mask = np.ones(len(vals), dtype=bool)
                    
                    if mask.any():
                        matrices[field][t_indices[mask], n_indices[mask]] = vals[mask]
            
            t_matrix_end = time.perf_counter()
            logger.info(f"[PolarsLoaderV4] 构建矩阵: {(t_matrix_end - t_matrix_start)*1000:.1f}ms")
            
            t_total = time.perf_counter() - t_start
            logger.info(f"[PolarsLoaderV4] 总计: {t_total*1000:.1f}ms, T={T}, N={N}")
            
            return {
                'matrices': matrices,
                'trading_dates': trading_dates,
                'stock_codes': stock_codes,
                'T': T,
                'N': N
            }
            
        except Exception as e:
            logger.error(f"[PolarsLoaderV4] 加载失败: {e}", exc_info=True)
            return None


# 全局实例
_polars_loader_v4: Optional[PolarsDataLoaderV4] = None

def get_polars_loader_v4(parquet_dir: str = "data/parquet_data") -> PolarsDataLoaderV4:
    """获取全局 Polars 数据加载器 V4 实例"""
    global _polars_loader_v4
    if _polars_loader_v4 is None:
        _polars_loader_v4 = PolarsDataLoaderV4(parquet_dir)
    return _polars_loader_v4
