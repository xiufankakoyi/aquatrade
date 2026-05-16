"""
Polars 数据加载器 V6 - 带缓存和因子预计算优化

核心优化：
1. 集成 MatrixCacheManager - 矩阵数据缓存
2. 集成 FactorPrecomputeEngine - 因子预计算
3. 智能预加载 - 基于回测日期预测
4. 批量因子计算 - 减少重复计算
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl

from config.logger import get_logger

logger = get_logger(__name__)


class PolarsDataLoaderV6:
    """
    Polars 数据加载器 V6 - 带缓存优化
    
    在 V5 基础上增加：
    - 矩阵缓存 (L1内存 + L2磁盘)
    - 因子预计算和缓存
    - 批量因子接口
    """
    
    def __init__(
        self,
        parquet_dir: str = "data/parquet_data",
        enable_cache: bool = True,
        enable_factor_precompute: bool = True
    ):
        self.parquet_dir = Path(parquet_dir)
        self.enable_cache = enable_cache
        self.enable_factor_precompute = enable_factor_precompute
        
        # 初始化缓存管理器
        self._cache_manager = None
        self._factor_engine = None
        
        if enable_cache:
            try:
                from data_svc.database.matrix_cache_manager import get_matrix_cache_manager
                self._cache_manager = get_matrix_cache_manager()
                logger.info("[PolarsLoaderV6] 矩阵缓存已启用")
            except Exception as e:
                logger.warning(f"[PolarsLoaderV6] 缓存初始化失败: {e}")
        
        if enable_factor_precompute:
            try:
                from core.strategies.utils.factor_precompute import get_factor_engine
                self._factor_engine = get_factor_engine()
                logger.info("[PolarsLoaderV6] 因子预计算已启用")
            except Exception as e:
                logger.warning(f"[PolarsLoaderV6] 因子引擎初始化失败: {e}")
    
    def load_period_to_matrix(
        self,
        start_date: str,
        end_date: str,
        required_fields: Optional[List[str]] = None,
        include_limit_status: bool = False,
        stock_pool: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        加载数据矩阵 (带缓存)
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            required_fields: 需要的字段
            include_limit_status: 是否包含涨跌停信息
            stock_pool: 股票池标识
            
        Returns:
            矩阵数据字典
        """
        t_start = time.perf_counter()
        
        if required_fields is None:
            required_fields = ['open', 'high', 'low', 'close', 'volume']
        
        fields_tuple = tuple(sorted(required_fields))
        
        # 1. 尝试从缓存获取
        if self.enable_cache and self._cache_manager is not None:
            cached_data = self._cache_manager.get(
                start_date, end_date, fields_tuple, stock_pool
            )
            if cached_data is not None:
                t_cache = time.perf_counter()
                logger.info(
                    f"[PolarsLoaderV6] 缓存命中: {(t_cache-t_start)*1000:.1f}ms"
                )
                return cached_data
        
        # 2. 从数据源加载 (使用 V5 逻辑)
        data = self._load_from_source(
            start_date, end_date, required_fields, include_limit_status
        )
        
        if data is None:
            return None
        
        # 3. 存入缓存
        if self.enable_cache and self._cache_manager is not None:
            self._cache_manager.set(
                start_date, end_date, fields_tuple, data, stock_pool
            )
        
        t_end = time.perf_counter()
        logger.info(f"[PolarsLoaderV6] 加载完成: {(t_end-t_start)*1000:.1f}ms")
        
        return data
    
    def load_with_factors(
        self,
        start_date: str,
        end_date: str,
        base_fields: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        加载数据并预计算因子
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            base_fields: 基础字段
            factor_names: 需要的因子列表
            
        Returns:
            包含基础数据和因子的字典
        """
        t_start = time.perf_counter()
        
        # 1. 加载基础数据
        base_data = self.load_period_to_matrix(
            start_date, end_date, base_fields or ['open', 'high', 'low', 'close', 'volume']
        )
        
        if base_data is None:
            return None
        
        # 2. 计算因子
        if factor_names and self.enable_factor_precompute and self._factor_engine is not None:
            close_matrix = base_data['matrices'].get('close')
            
            if close_matrix is not None:
                factors = self._factor_engine.compute_factors(
                    close_matrix=close_matrix,
                    factor_names=factor_names,
                    date_range=(start_date, end_date)
                )
                
                # 合并因子到结果
                base_data['factors'] = factors
                
                t_end = time.perf_counter()
                logger.info(
                    f"[PolarsLoaderV6] 数据+因子加载完成: {(t_end-t_start)*1000:.1f}ms, "
                    f"因子: {list(factors.keys())}"
                )
        
        return base_data
    
    def preload_for_backtest(
        self,
        start_date: str,
        end_date: str,
        warmup_days: int = 60
    ) -> Dict[str, Any]:
        """
        为回测预加载数据
        
        自动加载预热期数据，确保指标计算有足够历史
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
            warmup_days: 预热天数
            
        Returns:
            预加载统计
        """
        t_start = time.perf_counter()
        
        # 计算预热期开始日期
        try:
            from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
            loader_v5 = get_polars_loader_v5()
            
            # 获取交易日历
            all_dates = loader_v5.get_trading_dates("2020-01-01", end_date)
            start_idx = all_dates.index(start_date) if start_date in all_dates else 0
            warmup_start_idx = max(0, start_idx - warmup_days)
            warmup_start = all_dates[warmup_start_idx]
            
        except Exception:
            # 降级：简单日期计算
            from datetime import datetime, timedelta
            warmup_start = (
                datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=warmup_days*1.5)
            ).strftime("%Y-%m-%d")
        
        # 预加载数据
        data = self.load_period_to_matrix(warmup_start, end_date)
        
        t_end = time.perf_counter()
        
        result = {
            "status": "success" if data else "failed",
            "load_time_ms": round((t_end - t_start) * 1000, 2),
            "date_range": {"start": warmup_start, "end": end_date},
            "matrix_shape": f"{data['T']}x{data['N']}" if data else None
        }
        
        logger.info(f"[PolarsLoaderV6] 预加载完成: {result}")
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = {"cache_enabled": self.enable_cache}
        
        if self._cache_manager is not None:
            stats.update(self._cache_manager.get_stats())
        
        return stats
    
    def get_factor_for_stock(
        self,
        stock_code: str,
        trade_date: str,
        factor_names: List[str]
    ) -> Dict[str, float]:
        """
        获取单只股票在某日期的因子值
        
        供回测引擎调用，将矩阵因子转换为逐股票格式
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            factor_names: 因子名称列表
            
        Returns:
            因子值字典
        """
        result = {}
        
        # 从缓存或内存中获取因子矩阵
        if not hasattr(self, '_current_factor_cache'):
            return result
        
        factor_cache = self._current_factor_cache
        
        for factor_name in factor_names:
            if factor_name not in factor_cache:
                continue
            
            factor_matrix = factor_cache[factor_name]
            
            # 获取日期和股票索引
            if 'trading_dates' not in factor_cache or 'stock_codes' not in factor_cache:
                continue
            
            try:
                date_idx = factor_cache['trading_dates'].index(trade_date)
                stock_idx = factor_cache['stock_codes'].index(stock_code)
                result[factor_name] = float(factor_matrix[date_idx, stock_idx])
            except (ValueError, IndexError):
                result[factor_name] = 0.0
        
        return result
    
    def prepare_factors_for_backtest(
        self,
        start_date: str,
        end_date: str,
        factor_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        为回测准备因子数据
        
        预计算所有需要的因子，存储在内存中供快速查询
        
        Returns:
            因子数据字典，包含矩阵和索引信息
        """
        if not factor_names or not self.enable_factor_precompute:
            return None
        
        t_start = time.perf_counter()
        
        # 加载基础数据（含预热期）
        data = self.load_period_to_matrix(
            start_date, end_date, ['close']
        )
        
        if data is None:
            return None
        
        close_matrix = data['matrices']['close']
        
        # 计算所有因子
        factors = self._factor_engine.compute_factors(
            close_matrix=close_matrix,
            factor_names=factor_names,
            date_range=(start_date, end_date)
        )
        
        # 存储到缓存
        self._current_factor_cache = {
            **factors,
            'trading_dates': data['trading_dates'],
            'stock_codes': data['stock_codes']
        }
        
        t_end = time.perf_counter()
        logger.info(
            f"[PolarsLoaderV6] 回测因子准备完成: {(t_end-t_start)*1000:.1f}ms, "
            f"因子: {list(factors.keys())}"
        )
        
        return self._current_factor_cache
    
    def clear_cache(self) -> None:
        """清除缓存"""
        if self._cache_manager is not None:
            self._cache_manager.clear_all()
            logger.info("[PolarsLoaderV6] 矩阵缓存已清除")
        
        if self._factor_engine is not None:
            self._factor_engine.clear_cache()
            logger.info("[PolarsLoaderV6] 因子缓存已清除")
    
    def _load_from_source(
        self,
        start_date: str,
        end_date: str,
        required_fields: List[str],
        include_limit_status: bool
    ) -> Optional[Dict[str, Any]]:
        """
        从数据源加载 (V5 逻辑)
        """
        try:
            from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
            loader_v5 = get_polars_loader_v5()
            
            return loader_v5.load_period_to_matrix(
                start_date=start_date,
                end_date=end_date,
                required_fields=required_fields,
                include_limit_status=include_limit_status
            )
            
        except Exception as e:
            logger.error(f"[PolarsLoaderV6] 加载失败: {e}")
            return None


# 全局实例
_polars_loader_v6: Optional[PolarsDataLoaderV6] = None


def get_polars_loader_v6(
    parquet_dir: str = "data/parquet_data",
    enable_cache: bool = True,
    enable_factor_precompute: bool = True
) -> PolarsDataLoaderV6:
    """获取全局 Polars 数据加载器 V6 实例"""
    global _polars_loader_v6
    if _polars_loader_v6 is None:
        _polars_loader_v6 = PolarsDataLoaderV6(
            parquet_dir=parquet_dir,
            enable_cache=enable_cache,
            enable_factor_precompute=enable_factor_precompute
        )
    return _polars_loader_v6
