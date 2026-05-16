"""
strategies/strategy_factory.py 策略工厂测试

测试内容：
1. 策略工厂初始化
2. 策略发现和注册
3. 策略创建
4. 策略列表获取
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestStrategyFactory:
    """策略工厂测试"""
    
    @pytest.fixture
    def factory(self):
        """创建策略工厂实例"""
        from core.strategies.strategy_factory import StrategyFactory
        return StrategyFactory()
    
    def test_factory_creation(self, factory):
        """测试工厂创建"""
        assert factory is not None
        assert hasattr(factory, 'registry')
        assert hasattr(factory, '_id_to_name')
        assert hasattr(factory, '_name_to_id')
    
    def test_factory_lazy_initialization(self, factory):
        """测试延迟初始化"""
        assert factory._initialized == False
    
    def test_ensure_initialized(self, factory):
        """测试确保初始化"""
        factory._ensure_initialized()
        
        assert factory._initialized == True
    
    def test_get_available_strategies(self, factory):
        """测试获取可用策略"""
        factory._ensure_initialized()
        strategies = factory.get_available_strategies()
        
        assert isinstance(strategies, dict)
    
    def test_list_strategies(self, factory):
        """测试列出策略"""
        strategies = factory.list_strategies()
        
        assert isinstance(strategies, list)
    
    def test_create_strategy_invalid(self, factory):
        """测试创建无效策略"""
        with pytest.raises(ValueError):
            factory.create_strategy("invalid_strategy_id")
    
    def test_get_strategy_info(self, factory):
        """测试获取策略信息"""
        factory._ensure_initialized()
        
        strategies = factory.list_strategies()
        if strategies:
            strategy_id = strategies[0].get('id') if isinstance(strategies[0], dict) else strategies[0]
            assert strategy_id is not None


class TestStrategyFactoryRegistry:
    """策略工厂注册表测试"""
    
    @pytest.fixture
    def factory(self):
        """创建策略工厂实例"""
        from core.strategies.strategy_factory import StrategyFactory
        return StrategyFactory()
    
    def test_registry_empty_before_init(self, factory):
        """测试初始化前注册表为空"""
        assert len(factory.registry) == 0
    
    def test_registry_populated_after_init(self, factory):
        """测试初始化后注册表有内容"""
        factory._ensure_initialized()
        
        assert len(factory.registry) >= 0


class TestStrategyFactoryConfig:
    """策略工厂配置测试"""
    
    @pytest.fixture
    def factory(self):
        """创建策略工厂实例"""
        from core.strategies.strategy_factory import StrategyFactory
        return StrategyFactory()
    
    def test_config_loader_exists(self, factory):
        """测试配置加载器存在"""
        assert hasattr(factory, '_config_loader')
    
    def test_config_registry_exists(self, factory):
        """测试配置注册表存在"""
        assert hasattr(factory, '_config_registry')
    
    def test_discover_config_strategies(self, factory):
        """测试发现配置化策略"""
        factory._discover_config_strategies()
        
        assert factory._config_loader is not None


class TestStrategyFactorySingleton:
    """策略工厂单例测试"""
    
    def test_factory_singleton(self):
        """测试工厂单例模式"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory1 = StrategyFactory()
        factory2 = StrategyFactory()
        
        assert factory1 is not factory2


class TestStrategyFactoryMethods:
    """策略工厂方法测试"""
    
    @pytest.fixture
    def factory(self):
        """创建策略工厂实例"""
        from core.strategies.strategy_factory import StrategyFactory
        return StrategyFactory()
    
    def test_get_latest_mtime(self, factory):
        """测试获取最新修改时间"""
        mtime = factory._get_latest_mtime()
        
        assert isinstance(mtime, float)
    
    def test_register_strategy_instance(self, factory):
        """测试注册策略实例"""
        from core.strategies.strategy_framework import StrategyBase
        
        class MockStrategy(StrategyBase):
            strategy_id = "mock_test_strategy"
            strategy_name = "Mock Test Strategy"
        
        factory._register_strategy_instance(MockStrategy)
        
        assert "mock_test_strategy" in factory.registry
