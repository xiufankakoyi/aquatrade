"""
core/strategies/utils/smart_factor_loader.py 智能因子加载器测试

测试内容：
1. 单例模式
2. 数据库因子映射
3. 计算因子配置
4. 缓存功能
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import threading


class TestDBAvailableFactors:
    """数据库可用因子测试"""
    
    def test_price_factors(self):
        """测试价格因子"""
        from core.strategies.utils.smart_factor_loader import DB_AVAILABLE_FACTORS
        
        assert 'close' in DB_AVAILABLE_FACTORS
        assert 'open' in DB_AVAILABLE_FACTORS
        assert 'high' in DB_AVAILABLE_FACTORS
        assert 'low' in DB_AVAILABLE_FACTORS
    
    def test_volume_factors(self):
        """测试成交量因子"""
        from core.strategies.utils.smart_factor_loader import DB_AVAILABLE_FACTORS
        
        assert 'volume' in DB_AVAILABLE_FACTORS
        assert 'amount' in DB_AVAILABLE_FACTORS
        assert 'volume_ratio' in DB_AVAILABLE_FACTORS
        assert 'turnover_rate' in DB_AVAILABLE_FACTORS
    
    def test_ma_factors(self):
        """测试均线因子"""
        from core.strategies.utils.smart_factor_loader import DB_AVAILABLE_FACTORS
        
        assert 'ma5' in DB_AVAILABLE_FACTORS
        assert 'ma10' in DB_AVAILABLE_FACTORS
        assert 'ma20' in DB_AVAILABLE_FACTORS
    
    def test_market_value_factors(self):
        """测试市值因子"""
        from core.strategies.utils.smart_factor_loader import DB_AVAILABLE_FACTORS
        
        assert 'total_mv' in DB_AVAILABLE_FACTORS
        assert 'float_mv' in DB_AVAILABLE_FACTORS
        assert 'pe' in DB_AVAILABLE_FACTORS
        assert 'pb' in DB_AVAILABLE_FACTORS


class TestComputeFactors:
    """计算因子配置测试"""
    
    def test_rsi_factors(self):
        """测试 RSI 因子配置"""
        from core.strategies.utils.smart_factor_loader import COMPUTE_FACTORS
        
        assert 'rsi_6' in COMPUTE_FACTORS
        assert 'rsi_14' in COMPUTE_FACTORS
        assert 'rsi_24' in COMPUTE_FACTORS
        
        rsi_14 = COMPUTE_FACTORS['rsi_14']
        assert 'close' in rsi_14['deps']
        assert rsi_14['params']['period'] == 14
    
    def test_kdj_factors(self):
        """测试 KDJ 因子配置"""
        from core.strategies.utils.smart_factor_loader import COMPUTE_FACTORS
        
        assert 'kdj_k' in COMPUTE_FACTORS
        assert 'kdj_d' in COMPUTE_FACTORS
        assert 'kdj_j' in COMPUTE_FACTORS
        
        kdj_k = COMPUTE_FACTORS['kdj_k']
        assert 'high' in kdj_k['deps']
        assert 'low' in kdj_k['deps']
        assert 'close' in kdj_k['deps']
    
    def test_macd_factors(self):
        """测试 MACD 因子配置"""
        from core.strategies.utils.smart_factor_loader import COMPUTE_FACTORS
        
        assert 'macd_dif' in COMPUTE_FACTORS
        assert 'macd_dea' in COMPUTE_FACTORS
        assert 'macd_hist' in COMPUTE_FACTORS
        
        macd_dif = COMPUTE_FACTORS['macd_dif']
        assert macd_dif['params']['fast'] == 12
        assert macd_dif['params']['slow'] == 26
    
    def test_boll_factors(self):
        """测试布林带因子配置"""
        from core.strategies.utils.smart_factor_loader import COMPUTE_FACTORS
        
        assert 'boll_upper' in COMPUTE_FACTORS
        assert 'boll_mid' in COMPUTE_FACTORS
        assert 'boll_lower' in COMPUTE_FACTORS
    
    def test_gain_factors(self):
        """测试涨幅因子配置"""
        from core.strategies.utils.smart_factor_loader import COMPUTE_FACTORS
        
        assert 'gain_1d' in COMPUTE_FACTORS
        assert 'gain_3d' in COMPUTE_FACTORS
        assert 'gain_5d' in COMPUTE_FACTORS
        assert 'gain_10d' in COMPUTE_FACTORS


class TestSmartFactorLoaderSingleton:
    """单例模式测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader1 = SmartFactorLoader()
        loader2 = SmartFactorLoader()
        
        assert loader1 is loader2
    
    def test_singleton_thread_safety(self):
        """测试单例线程安全"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        instances = []
        
        def create_instance():
            instances.append(SmartFactorLoader())
        
        threads = [threading.Thread(target=create_instance) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert all(inst is instances[0] for inst in instances)


class TestSmartFactorLoaderCache:
    """缓存功能测试"""
    
    def test_clear_cache(self):
        """测试清除缓存"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader = SmartFactorLoader()
        loader._factor_cache[(1, 'test')] = np.array([1, 2, 3])
        
        loader.clear_cache()
        
        assert len(loader._factor_cache) == 0
        assert len(loader._strategy_data) == 0
    
    def test_register_strategy_data(self):
        """测试注册策略数据"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader = SmartFactorLoader()
        loader.clear_cache()
        
        data = {
            'close': np.random.randn(10, 3).astype(np.float32),
            'volume': np.random.randn(10, 3).astype(np.float32)
        }
        
        loader.register_strategy_data(12345, data)
        
        assert 12345 in loader._strategy_data
        assert loader._strategy_data[12345] == data


class TestSmartFactorLoaderGetFactor:
    """获取因子测试"""
    
    def test_get_factor_db_factor(self):
        """测试获取数据库因子"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader = SmartFactorLoader()
        loader.clear_cache()
        
        data = {
            'close': np.random.randn(10, 3).astype(np.float32),
            'ma5': np.random.randn(10, 3).astype(np.float32)
        }
        
        loader.register_strategy_data(99999, data)
        
        result = loader.get_factor('close', 99999)
        
        assert result is not None
        assert result.shape == (10, 3)
    
    def test_get_factor_missing_strategy(self):
        """测试获取未注册策略的因子"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader = SmartFactorLoader()
        loader.clear_cache()
        
        result = loader.get_factor('close', 88888)
        
        assert result is None
    
    def test_get_factor_with_strategy_data(self):
        """测试带策略数据获取因子"""
        from core.strategies.utils.smart_factor_loader import SmartFactorLoader
        
        loader = SmartFactorLoader()
        loader.clear_cache()
        
        data = {
            'close': np.random.randn(10, 3).astype(np.float32)
        }
        
        result = loader.get_factor('close', 77777, strategy_data=data)
        
        assert result is not None


class TestNumbaAvailability:
    """Numba 可用性测试"""
    
    def test_numba_available_flag(self):
        """测试 Numba 可用性标志"""
        from core.strategies.utils.smart_factor_loader import NUMBA_AVAILABLE
        
        assert isinstance(NUMBA_AVAILABLE, bool)
    
    def test_njit_decorator(self):
        """测试 njit 装饰器"""
        from core.strategies.utils.smart_factor_loader import njit
        
        @njit
        def test_func(x):
            return x + 1
        
        result = test_func(1)
        
        assert result == 2
    
    def test_prange_available(self):
        """测试 prange 可用性"""
        from core.strategies.utils.smart_factor_loader import prange
        
        result = sum(i for i in prange(5))
        
        assert result == 10
