"""
Polars 数据加载器 V5 - 极致精简版

核心优化：
1. 只读取必要的字段（最小化 I/O）
2. 跳过 limit_status（如果不需要涨跌停信息）
3. 使用更高效的矩阵构建方法
"""
import numpy as np
import polars as pl
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import logging
import time

logger = logging.getLogger(__name__)


class PolarsDataLoaderV5:
    """
    极致精简 Polars 数据加载器 V5
    
    只读取必要字段，跳过不必要的 Join
    """
    
    def __init__(self, parquet_dir: str = "data/parquet_data"):
        self.parquet_dir = Path(parquet_dir)
        
    def load_period_to_matrix(
        self,
        start_date: str,
        end_date: str,
        required_fields: Optional[List[str]] = None,
        include_limit_status: bool = False,  # 默认不读取涨跌停信息（加速）
        use_adj_price: bool = False  # 默认不使用复权价格（MA策略通常用不复权）
    ) -> Optional[Dict]:
        """
        加载指定时间段的数据，直接构建矩阵（极致精简版本）
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            required_fields: 需要的字段列表
            include_limit_status: 是否包含涨跌停信息（默认 False，加速）
            
        Returns:
            包含矩阵数据的字典，或 None 如果加载失败
        """
        t_start = time.perf_counter()
        
        if required_fields is None:
            required_fields = ['open', 'high', 'low', 'close', 'volume']
        
        try:
            daily_path = self.parquet_dir / "stock_daily.parquet"
            info_path = self.parquet_dir / "stock_info.parquet"
            
            t_read_start = time.perf_counter()
            
            # 【极致优化】最小化字段读取
            # 使用ts_code而不是stock_code，因为ts_code包含正确的6位股票代码
            base_cols = ['ts_code', 'trade_date']
            
            # 只选择必要的字段
            daily_fields = []
            for f in required_fields:
                if f not in ['is_st', 'is_kc', 'is_cy']:
                    daily_fields.append(f)
            
            # 如果需要复权价格，必须读取adj_factor
            if use_adj_price and 'adj_factor' not in daily_fields:
                daily_fields.append('adj_factor')
            
            select_cols = base_cols + daily_fields
            
            # 大表使用 scan_parquet + filter pushdown
            lf_daily = pl.scan_parquet(daily_path)
            lf_daily = lf_daily.filter(
                (pl.col('trade_date') >= start_date) &
                (pl.col('trade_date') <= end_date) &
                (pl.col('volume') > 0) &
                (pl.col('close').is_not_null())
            )
            lf_daily = lf_daily.select(select_cols)
            df_daily = lf_daily.collect()
            
            # 从ts_code提取股票代码（去掉.SZ/.SH后缀）
            df_daily = df_daily.with_columns([
                pl.col('ts_code').str.replace(r'\.SZ$', '').str.replace(r'\.SH$', '').alias('stock_code')
            ])
            df_daily = df_daily.drop('ts_code')
            
            # 小表使用 read_parquet
            info_cols = ['stock_code']
            if 'is_kc' in required_fields or 'is_cy' in required_fields or 'is_st' in required_fields:
                info_cols = ['stock_code', 'is_kc', 'is_cy', 'is_st']
            
            if len(info_cols) > 1:
                df_info = pl.read_parquet(info_path)
                df_info = df_info.select(info_cols)
            else:
                df_info = None
            
            t_read_end = time.perf_counter()
            logger.info(f"[PolarsLoaderV5] 读取: {(t_read_end - t_read_start)*1000:.1f}ms, daily={len(df_daily)}")
            
            if df_daily.is_empty():
                logger.warning(f"[PolarsLoaderV5] 无数据: {start_date} 到 {end_date}")
                return None
            
            # Join（如果需要）
            t_join_start = time.perf_counter()
            
            if df_info is not None:
                df_result = df_daily.join(df_info, on='stock_code', how='left')
                # 填充缺失值
                for col in ['is_st', 'is_kc', 'is_cy']:
                    if col in df_result.columns:
                        df_result = df_result.with_columns(pl.col(col).fill_null(0))
                    elif col in required_fields:
                        df_result = df_result.with_columns(pl.lit(0).alias(col))
            else:
                df_result = df_daily
            
            t_join_end = time.perf_counter()
            logger.info(f"[PolarsLoaderV5] Join: {(t_join_end - t_join_start)*1000:.1f}ms")
            
            # 构建矩阵
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
            
            # 初始化矩阵
            all_fields = required_fields.copy()
            if include_limit_status:
                all_fields.extend(['is_limit_up', 'is_limit_down', 'is_suspended'])
            
            matrices = {}
            
            for field in all_fields:
                if field in ['is_st', 'is_kc', 'is_cy', 'is_limit_up', 'is_limit_down', 'is_suspended']:
                    matrices[field] = np.full((T, N), 0, dtype=np.int8)
                else:
                    matrices[field] = np.full((T, N), np.nan, dtype=np.float32)
            
            # 如果使用复权价格，计算相对复权价格
            # 聚宽使用"动态复权"：以回测期间最后一天为基准
            if use_adj_price and 'adj_factor' in df_result.columns:
                # 计算每只股票最后一天的adj_factor作为基准
                last_adj = df_result.group_by('stock_code').agg(
                    pl.col('adj_factor').last().alias('last_adj_factor')
                )
                df_result = df_result.join(last_adj, on='stock_code')
                
                # 相对复权：原始价格 * adj_factor / last_adj_factor
                price_fields = ['open', 'high', 'low', 'close', 'prev_close']
                for pf in price_fields:
                    if pf in df_result.columns:
                        df_result = df_result.with_columns(
                            (pl.col(pf) * pl.col('adj_factor') / pl.col('last_adj_factor')).alias(pf)
                        )
                
                df_result = df_result.drop('last_adj_factor')
            
            # 批量填充
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
            logger.info(f"[PolarsLoaderV5] 构建矩阵: {(t_matrix_end - t_matrix_start)*1000:.1f}ms")
            
            t_total = time.perf_counter() - t_start
            logger.info(f"[PolarsLoaderV5] 总计: {t_total*1000:.1f}ms, T={T}, N={N}")
            
            return {
                'matrices': matrices,
                'trading_dates': trading_dates,
                'stock_codes': stock_codes,
                'T': T,
                'N': N
            }
            
        except Exception as e:
            logger.error(f"[PolarsLoaderV5] 加载失败: {e}", exc_info=True)
            return None


# 全局实例
_polars_loader_v5: Optional[PolarsDataLoaderV5] = None

def get_polars_loader_v5(parquet_dir: str = "data/parquet_data") -> PolarsDataLoaderV5:
    """获取全局 Polars 数据加载器 V5 实例"""
    global _polars_loader_v5
    if _polars_loader_v5 is None:
        _polars_loader_v5 = PolarsDataLoaderV5(parquet_dir)
    return _polars_loader_v5
