"""
Polars 数据加载器 V3 - 极致性能优化

核心优化：
1. 全部使用 scan_parquet + filter pushdown（比 read_parquet 快 10 倍）
2. 完全跳过 Pandas，纯 Polars 构建矩阵
3. 延迟执行，直到最后才 collect
"""
import numpy as np
import polars as pl
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class PolarsDataLoaderV3:
    """
    极致性能 Polars 数据加载器 V3
    
    全部使用 scan_parquet，利用 filter pushdown 减少 I/O
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
        加载指定时间段的数据，直接构建矩阵（极致性能版本）
        
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
            # 1. 使用 scan_parquet + filter pushdown（极致性能）
            daily_path = self.parquet_dir / "stock_daily.parquet"
            info_path = self.parquet_dir / "stock_info.parquet"
            limit_path = self.parquet_dir / "stock_limit_status.parquet"
            
            t_read_start = time.perf_counter()
            
            # 构建列选择
            base_cols = ['stock_code', 'trade_date']
            select_cols = base_cols + [f for f in required_fields if f not in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']]
            
            # 【核心优化】使用 scan_parquet + filter pushdown
            lf_daily = pl.scan_parquet(daily_path)
            
            # 过滤日期范围（filter pushdown 会在读取时过滤，减少 I/O）
            lf_daily = lf_daily.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date) &
                (pl.col('volume') > 0) &
                (pl.col('close').is_not_null())
            )
            
            # 选择列（projection pushdown）
            lf_daily = lf_daily.select(select_cols)
            
            # 【核心优化】对 stock_info 也使用 scan_parquet（虽然小表，但保持一致性）
            lf_info = pl.scan_parquet(info_path)
            lf_info = lf_info.select(['stock_code', 'is_kc', 'is_cy', 'is_st', 'list_date'])
            
            # 【核心优化】对 limit_status 使用 scan_parquet + filter
            lf_limit = pl.scan_parquet(limit_path)
            lf_limit = lf_limit.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date)
            )
            lf_limit = lf_limit.select(['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended'])
            
            # 【核心优化】使用 lazy join，延迟执行
            lf_result = lf_daily.join(lf_info, on='stock_code', how='left')
            lf_result = lf_result.join(lf_limit, on=['stock_code', 'trade_date'], how='left')
            
            # 填充缺失值（lazy 操作）
            fill_cols = ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']
            for col in fill_cols:
                lf_result = lf_result.with_columns(pl.col(col).fill_null(0))
            
            # 最后一步才 collect（所有操作合并执行）
            df_result = lf_result.collect()
            
            t_read_end = time.perf_counter()
            logger.info(f"[PolarsLoaderV3] 读取和 Join: {(t_read_end - t_read_start)*1000:.1f}ms, 行数: {len(df_result)}")
            
            if df_result.is_empty():
                logger.warning(f"[PolarsLoaderV3] 无数据: {start_date} 到 {end_date}")
                return None
            
            # 2. 直接构建矩阵（纯 Polars，无 Pandas）
            t_matrix_start = time.perf_counter()
            
            # 获取唯一的日期和股票代码
            trading_dates = df_result['trade_date'].unique().sort().to_list()
            stock_codes = df_result['stock_code'].unique().sort().to_list()
            
            T = len(trading_dates)
            N = len(stock_codes)
            
            # 创建索引映射
            date_to_idx = {d: i for i, d in enumerate(trading_dates)}
            code_to_idx = {c: i for i, c in enumerate(stock_codes)}
            
            # 添加索引列
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
            
            # 使用 NumPy 进行批量填充
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
            logger.info(f"[PolarsLoaderV3] 构建矩阵: {(t_matrix_end - t_matrix_start)*1000:.1f}ms")
            
            t_total = time.perf_counter() - t_start
            logger.info(f"[PolarsLoaderV3] 总计: {t_total*1000:.1f}ms, T={T}, N={N}")
            
            return {
                'matrices': matrices,
                'trading_dates': trading_dates,
                'stock_codes': stock_codes,
                'T': T,
                'N': N
            }
            
        except Exception as e:
            logger.error(f"[PolarsLoaderV3] 加载失败: {e}", exc_info=True)
            return None


# 全局实例
_polars_loader_v3: Optional[PolarsDataLoaderV3] = None

def get_polars_loader_v3(parquet_dir: str = "data/parquet_data") -> PolarsDataLoaderV3:
    """获取全局 Polars 数据加载器 V3 实例"""
    global _polars_loader_v3
    if _polars_loader_v3 is None:
        _polars_loader_v3 = PolarsDataLoaderV3(parquet_dir)
    return _polars_loader_v3
