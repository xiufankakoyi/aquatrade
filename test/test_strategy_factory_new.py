"""
core/strategies/strategy_factory.py 策略工厂测试

测试内容：
1. 策略工厂初始化
2. 策略注册与发现
3. 策略创建
4. 配置化策略
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys


class TestStrategyFactoryInit:
    """策略工厂初始化测试"""
    
    def test_init_default(self):
        """测试默认初始化"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        assert factory.registry == {}
        assert factory._id_to_name == {}
        assert factory._name_to_id == {}
        assert factory._initialized is False
    
    def test_lazy_initialization(self):
        """测试延迟初始化"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        
        assert factory._initialized is False
        
        factory._ensure_initialized()
        
        assert factory._initialized is True


class TestStrategyFactoryRegistry:
    """策略工厂注册测试"""
    
    def test_register_strategy_instance(self):
        """测试注册策略实例"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        
        mock_strategy_class = Mock()
        mock_strategy_class.__module__ = "test_module"
        mock_strategy_class.__name__ = "TestStrategy"
        mock_strategy_class.strategy_id = "test_strategy_001"
        mock_strategy_class.strategy_name = "测试策略"
        
        factory._register_strategy_instance(mock_strategy_class)
        
        assert "test_strategy_001" in factory.registry
        assert factory._id_to_name["test_strategy_001"] == "测试策略"
    
    def test_register_strategy_without_id(self):
        """测试注册无 ID 策略（使用名称）"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        
        mock_strategy_class = Mock()
        mock_strategy_class.__module__ = "test_module"
        mock_strategy_class.__name__ = "TestStrategy"
        mock_strategy_class.strategy_id = None
        mock_strategy_class.strategy_name = "测试策略"
        
        factory._register_strategy_instance(mock_strategy_class)
        
        assert "测试策略" in factory.registry
    
    def test_register_strategy_base_class_skipped(self):
        """测试基类不被注册"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        
        mock_strategy_class = Mock()
        mock_strategy_class.__module__ = "test_module"
        mock_strategy_class.__name__ = "BaseStrategy"
        mock_strategy_class.strategy_id = None
        mock_strategy_class.strategy_name = None
        
        factory._register_strategy_instance(mock_strategy_class)
        
        assert len(factory.registry) == 0
    
    def test_register_duplicate_strategy(self):
        """测试重复注册策略"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        
        mock_strategy_class1 = Mock()
        mock_strategy_class1.__module__ = "test_module1"
        mock_strategy_class1.__name__ = "TestStrategy1"
        mock_strategy_class1.strategy_id = "test_strategy"
        mock_strategy_class1.strategy_name = "测试策略1"
        
        mock_strategy_class2 = Mock()
        mock_strategy_class2.__module__ = "test_module2"
        mock_strategy_class2.__name__ = "TestStrategy2"
        mock_strategy_class2.strategy_id = "test_strategy"
        mock_strategy_class2.strategy_name = "测试策略2"
        
        factory._register_strategy_instance(mock_strategy_class1)
        factory._register_strategy_instance(mock_strategy_class2)
        
        assert factory.registry["test_strategy"] == mock_strategy_class1


class TestStrategyFactoryResolve:
    """策略工厂标识符解析测试"""
    
    def test_resolve_by_id_exists(self):
        """测试通过存在的 ID 解析"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        factory.registry = {
            "test_strategy": Mock(),
        }
        factory._id_to_name = {
            "test_strategy": "测试策略",
        }
        factory._name_to_id = {
            "测试策略": "test_strategy",
        }
        factory._strategies_mtime = float('inf')
        
        result = factory._resolve_identifier_to_id("test_strategy")
        
        assert result == "test_strategy"
    
    def test_resolve_by_name_exists(self):
        """测试通过存在的名称解析"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        factory.registry = {
            "test_strategy": Mock(),
        }
        factory._id_to_name = {
            "test_strategy": "测试策略",
        }
        factory._name_to_id = {
            "测试策略": "test_strategy",
        }
        factory._strategies_mtime = float('inf')
        
        result = factory._resolve_identifier_to_id("测试策略")
        
        assert result == "test_strategy"
    
    def test_resolve_not_found(self):
        """测试解析失败"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        factory.registry = {}
        factory._id_to_name = {}
        factory._name_to_id = {}
        factory._strategies_mtime = float('inf')
        
        result = factory._resolve_identifier_to_id("nonexistent")
        
        assert result is None


class TestStrategyFactoryCreate:
    """策略工厂创建策略测试"""
    
    def test_create_strategy_not_found(self):
        """测试创建不存在的策略"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        factory.registry = {}
        factory._id_to_name = {}
        factory._name_to_id = {}
        factory._config_registry = {}
        factory._strategies_mtime = 0
        
        with pytest.raises(ValueError):
            factory._create_strategy_instance("nonexistent")


class TestStrategyFactoryList:
    """策略工厂列表测试"""
    
    def test_list_strategies_returns_list(self):
        """测试列出策略返回列表"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        result = factory._list_strategies_instance()
        
        assert isinstance(result, list)
    
    def test_get_available_strategies_returns_dict(self):
        """测试获取可用策略返回字典"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        result = factory._get_available_strategies_instance()
        
        assert isinstance(result, dict)
    
    def test_get_strategy_by_id_not_found(self):
        """测试获取不存在的策略类"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        factory._initialized = True
        factory.registry = {}
        factory._strategies_mtime = 0
        
        result = factory._get_strategy_by_id_instance("nonexistent")
        
        assert result is None


class TestStrategyFactoryConfigStrategies:
    """策略工厂配置化策略测试"""
    
    def test_list_config_strategies_returns_list(self):
        """测试配置策略列表返回列表"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        result = factory.list_config_strategies()
        
        assert isinstance(result, list)
    
    def test_get_config_strategy_not_found(self):
        """测试获取不存在的配置策略"""
        from core.strategies.strategy_factory import StrategyFactory
        
        factory = StrategyFactory()
        result = factory.get_config_strategy("nonexistent")
        
        assert result is None
