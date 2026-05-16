"""
core/strategies/utils/factor_loader.py 因子加载器测试

测试内容：
1. FactorLoader 类方法
2. 因子注册表
3. 缓存功能
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestFactorLoaderDBFactors:
    """数据库因子测试"""
    
    def test_db_factors_contains_price(self):
        """测试价格因子"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'close' in FactorLoader.DB_FACTORS
        assert 'open' in FactorLoader.DB_FACTORS
        assert 'high' in FactorLoader.DB_FACTORS
        assert 'low' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_ma(self):
        """测试均线因子"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'ma5' in FactorLoader.DB_FACTORS
        assert 'ma10' in FactorLoader.DB_FACTORS
        assert 'ma20' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_technical(self):
        """测试技术指标因子"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'rsi_14' in FactorLoader.DB_FACTORS
        assert 'macd_dif' in FactorLoader.DB_FACTORS
        assert 'kdj_k' in FactorLoader.DB_FACTORS
    
    def test_db_factors_contains_boll(self):
        """测试布林带因子"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert 'boll_upper' in FactorLoader.DB_FACTORS
        assert 'boll_mid' in FactorLoader.DB_FACTORS
        assert 'boll_lower' in FactorLoader.DB_FACTORS


class TestFactorLoaderCache:
    """因子加载器缓存测试"""
    
    def test_clear_cache(self):
        """测试清除缓存"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        FactorLoader._compute_cache["test_key"] = np.array([1, 2, 3])
        
        FactorLoader.clear_cache()
        
        assert len(FactorLoader._compute_cache) == 0
    
    def test_get_cache_key(self):
        """测试缓存键生成"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        strategy = Mock()
        params = {"window": 5, "method": "ema"}
        
        key = FactorLoader._get_cache_key(strategy, "test_factor", params)
        
        assert "test_factor" in key
        assert "window=5" in key
        assert "method=ema" in key
    
    def test_compute_cache_dict(self):
        """测试计算型因子缓存字典"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert isinstance(FactorLoader._compute_cache, dict)


class TestFactorLoaderRegistry:
    """因子注册表测试"""
    
    def test_registry_path(self):
        """测试注册表路径"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        assert FactorLoader._registry_path is not None
        assert isinstance(FactorLoader._registry_path, Path)
    
    def test_load_registry_empty(self):
        """测试加载空注册表"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        FactorLoader._registry_cache = None
        
        with patch.object(Path, 'exists', return_value=False):
            registry = FactorLoader.load_registry()
            
            assert isinstance(registry, dict)
    
    def test_load_registry_cached(self):
        """测试注册表缓存"""
        from core.strategies.utils.factor_loader import FactorLoader
        
        FactorLoader._registry_cache = {"test": "data"}
        
        registry = FactorLoader.load_registry()
        
        assert registry == {"test": "data"}
