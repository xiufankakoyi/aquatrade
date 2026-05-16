"""
core/backtest/memory_efficient_engine.py 内存高效引擎测试

测试内容：
1. 内存配置常量
2. 可选依赖检测
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestMemoryConstants:
    """内存常量配置测试"""
    
    def test_max_memory_mb(self):
        """测试最大内存限制"""
        from core.backtest.memory_efficient_engine import MAX_MEMORY_MB
        
        assert MAX_MEMORY_MB == 2048
    
    def test_l1_cache_days(self):
        """测试L1缓存天数"""
        from core.backtest.memory_efficient_engine import L1_CACHE_DAYS
        
        assert L1_CACHE_DAYS == 5


class TestOptionalDependencies:
    """可选依赖测试"""
    
    def test_polars_available(self):
        """测试Polars可用性"""
        from core.backtest.memory_efficient_engine import POLARS_AVAILABLE
        
        assert isinstance(POLARS_AVAILABLE, bool)
    
    def test_numba_available(self):
        """测试Numba可用性"""
        from core.backtest.memory_efficient_engine import NUMBA_AVAILABLE
        
        assert isinstance(NUMBA_AVAILABLE, bool)
    
    def test_njit_decorator(self):
        """测试Numba装饰器"""
        from core.backtest.memory_efficient_engine import njit
        
        @njit
        def test_func(x):
            return x + 1
        
        result = test_func(1)
        
        assert result == 2
    
    def test_prange_available(self):
        """测试prange可用性"""
        from core.backtest.memory_efficient_engine import prange
        
        result = sum(i for i in prange(5))
        
        assert result == 10


class TestLogger:
    """日志测试"""
    
    def test_logger_available(self):
        """测试日志可用性"""
        from core.backtest.memory_efficient_engine import logger
        
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'warning')
