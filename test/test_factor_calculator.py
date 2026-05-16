"""
core/strategies/utils/factor_calculator.py 因子计算器测试

测试内容：
1. FactorData 数据容器
2. FactorCalculator 单例模式
3. 因子加载功能
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestFactorData:
    """因子数据容器测试"""
    
    def test_factor_data_init(self):
        """测试初始化"""
        from core.strategies.utils.factor_calculator import FactorData
        
        matrix = np.array([[1.0, 2.0], [3.0, 4.0]])
        factor_data = FactorData(
            factor_name="test_factor",
            matrix=matrix,
            source="db"
        )
        
        assert factor_data.factor_name == "test_factor"
        assert factor_data.source == "db"
        assert factor_data.shape == (2, 2)
    
    def test_factor_data_shape(self):
        """测试形状计算"""
        from core.strategies.utils.factor_calculator import FactorData
        
        matrix = np.ones((10, 5))
        factor_data = FactorData(
            factor_name="ma5",
            matrix=matrix,
            source="db"
        )
        
        assert factor_data.shape == (10, 5)


class TestFactorCalculatorSingleton:
    """因子计算器单例测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from core.strategies.utils.factor_calculator import FactorCalculator
        
        calc1 = FactorCalculator()
        calc2 = FactorCalculator()
        
        assert calc1 is calc2
    
    def test_get_available_factors(self):
        """测试获取可用因子"""
        from core.strategies.utils.factor_calculator import FactorCalculator
        
        calc = FactorCalculator()
        factors = calc.get_available_factors()
        
        assert isinstance(factors, set)
        assert 'ma5' in factors
        assert 'ma10' in factors
        assert 'rsi_14' in factors


class TestFactorCalculatorLoadFactors:
    """因子加载测试"""
    
    def test_load_factors_empty(self):
        """测试空因子列表"""
        from core.strategies.utils.factor_calculator import FactorCalculator
        
        calc = FactorCalculator()
        results = calc.load_factors(
            factor_names=[],
            trading_dates=['2024-01-01'],
            stock_codes=['000001.SZ']
        )
        
        assert results == {}
    
    def test_load_factors_missing(self):
        """测试缺失因子"""
        from core.strategies.utils.factor_calculator import FactorCalculator
        
        calc = FactorCalculator()
        results = calc.load_factors(
            factor_names=['nonexistent_factor'],
            trading_dates=['2024-01-01'],
            stock_codes=['000001.SZ']
        )
        
        assert 'nonexistent_factor' not in results


class TestFactorConstants:
    """因子常量测试"""
    
    def test_all_db_factors(self):
        """测试数据库因子集合"""
        from core.strategies.utils.factor_calculator import ALL_DB_FACTORS
        
        assert 'ma5' in ALL_DB_FACTORS
        assert 'ma10' in ALL_DB_FACTORS
        assert 'ma20' in ALL_DB_FACTORS
        assert 'rsi_14' in ALL_DB_FACTORS
        assert 'macd_dif' in ALL_DB_FACTORS
    
    def test_compute_factors(self):
        """测试计算因子集合"""
        from core.strategies.utils.factor_calculator import COMPUTE_FACTORS
        
        assert 'gain_1d' in COMPUTE_FACTORS
        assert 'gain_5d' in COMPUTE_FACTORS
        assert 'volatility_10' in COMPUTE_FACTORS
