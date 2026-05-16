"""
core/strategies/utils/factor_loader.py 因子加载器测试

测试内容：
1. FactorLoader DB_FACTORS 常量
2. FactorLoader 缓存功能
3. FactorLoader 工具方法
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestFactorLoaderConstants:
    """因子加载器常量测试"""
    
    def test_db_factors_contains_price(self):
        """测试数据库因子包含价格数据"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'close' in FactorLoader.DB_FACTORS
        assert 'open' in FactorLoader.DB_FACTORS
        assert 'high' in FactorLoader.DB_FACTORS
        assert 'low' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_volume(self):
        """测试数据库因子包含成交量数据"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'volume' in FactorLoader.DB_FACTORS
        assert 'amount' in FactorLoader.DB_FACTORS
        assert 'volume_ratio' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_ma(self):
        """测试数据库因子包含均线"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'ma5' in FactorLoader.DB_FACTORS
        assert 'ma10' in FactorLoader.DB_FACTORS
        assert 'ma20' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_indicators(self):
        """测试数据库因子包含技术指标"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'rsi_14' in FactorLoader.DB_FACTORS
        assert 'macd_dif' in FactorLoader.DB_FACTORS
        assert 'kdj_k' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_attributes(self):
        """测试数据库因子包含股票属性"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'is_st' in FactorLoader.DB_FACTORS
        assert 'is_kc' in FactorLoader.DB_FACTORS
        assert 'is_limit_up' in FactorLoader.DB_FACTORS


class TestFactorLoaderCache:
    """因子加载器缓存测试"""
    
    def test_clear_cache(self):
        """测试清除缓存"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        FactorLoader._compute_cache['test_key'] = np.array([1, 2, 3])
        
        FactorLoader.clear_cache()
        
        assert len(FactorLoader._compute_cache) == 0
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        mock_strategy = Mock()
        mock_strategy.__id__ = 12345
        
        key = FactorLoader._get_cache_key(
            mock_strategy,
            'ma5',
            {'window': 5}
        )
        
        assert isinstance(key, str)
        assert 'ma5' in key
    
    def test_compute_cache_dict(self):
        """测试计算缓存字典"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert isinstance(FactorLoader._compute_cache, dict)


class TestFactorLoaderMethods:
    """因子加载器方法测试"""
    
    def test_has_get_factor_method(self):
        """测试是否有 get_factor 方法"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert hasattr(FactorLoader, 'get_factor')
