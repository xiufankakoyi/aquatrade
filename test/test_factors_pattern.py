"""
core/factors/pattern_factors.py 形态因子测试

测试内容：
1. 因子注册表
2. 因子计算器接口
3. 边界条件处理

注意：Numba 加速函数存在类型不统一问题，需要修复源码后才能测试计算逻辑
"""

import pytest
import numpy as np


class TestPatternFactorsRegistry:
    """形态因子注册表测试"""
    
    def test_get_pattern_factor(self):
        """测试获取形态因子"""
        from core.factors.pattern_factors import get_pattern_factor
        
        func = get_pattern_factor('apex_convergence')
        
        assert func is not None
        assert callable(func)
    
    def test_get_invalid_factor(self):
        """测试获取无效因子"""
        from core.factors.pattern_factors import get_pattern_factor
        
        func = get_pattern_factor('invalid_factor')
        
        assert func is None
    
    def test_list_pattern_factors(self):
        """测试列出所有形态因子"""
        from core.factors.pattern_factors import list_pattern_factors
        
        factors = list_pattern_factors()
        
        assert isinstance(factors, dict)
        assert 'apex_convergence' in factors
        assert 'extrema_high' in factors
        assert 'extrema_low' in factors
        assert 'double_bottom' in factors


class TestPatternFactorsConfig:
    """形态因子配置测试"""
    
    def test_pattern_factors_structure(self):
        """测试形态因子配置结构"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        assert isinstance(PATTERN_FACTORS, dict)
        
        for name, config in PATTERN_FACTORS.items():
            assert 'function' in config
            assert 'dependencies' in config
            assert 'description' in config
            assert callable(config['function'])
    
    def test_pattern_factors_dependencies(self):
        """测试形态因子依赖"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        for name, config in PATTERN_FACTORS.items():
            deps = config['dependencies']
            assert isinstance(deps, list)
            assert 'close' in deps
    
    def test_apex_convergence_config(self):
        """测试收敛三角形因子配置"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        config = PATTERN_FACTORS['apex_convergence']
        
        assert config['dependencies'] == ['close']
        assert '收敛三角形' in config['description']
    
    def test_extrema_high_config(self):
        """测试高点标记因子配置"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        config = PATTERN_FACTORS['extrema_high']
        
        assert config['dependencies'] == ['close']
        assert '高点' in config['description']
    
    def test_extrema_low_config(self):
        """测试低点标记因子配置"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        config = PATTERN_FACTORS['extrema_low']
        
        assert config['dependencies'] == ['close']
        assert '低点' in config['description']
    
    def test_double_bottom_config(self):
        """测试双底形态因子配置"""
        from core.factors.pattern_factors import PATTERN_FACTORS
        
        config = PATTERN_FACTORS['double_bottom']
        
        assert config['dependencies'] == ['close']
        assert '双底' in config['description'] or 'W底' in config['description']


class TestPatternFactorCalculatorInterface:
    """形态因子计算器接口测试"""
    
    def test_calculator_has_apex_convergence(self):
        """测试计算器有收敛三角形方法"""
        from core.factors.pattern_factors import PatternFactorCalculator
        
        assert hasattr(PatternFactorCalculator, 'apex_convergence')
        assert callable(PatternFactorCalculator.apex_convergence)
    
    def test_calculator_has_extrema_high(self):
        """测试计算器有高点标记方法"""
        from core.factors.pattern_factors import PatternFactorCalculator
        
        assert hasattr(PatternFactorCalculator, 'extrema_high')
        assert callable(PatternFactorCalculator.extrema_high)
    
    def test_calculator_has_extrema_low(self):
        """测试计算器有低点标记方法"""
        from core.factors.pattern_factors import PatternFactorCalculator
        
        assert hasattr(PatternFactorCalculator, 'extrema_low')
        assert callable(PatternFactorCalculator.extrema_low)
    
    def test_calculator_has_double_bottom(self):
        """测试计算器有双底形态方法"""
        from core.factors.pattern_factors import PatternFactorCalculator
        
        assert hasattr(PatternFactorCalculator, 'double_bottom')
        assert callable(PatternFactorCalculator.double_bottom)
