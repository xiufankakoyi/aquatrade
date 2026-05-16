"""
core/strategies/configurable/strategy_config.py 策略配置测试

测试内容：
1. ParameterConfig 参数配置
2. IndicatorConfig 指标配置
3. StrategyConfig 策略配置
"""

import pytest
from dataclasses import asdict


class TestParameterType:
    """参数类型枚举测试"""
    
    def test_parameter_types(self):
        """测试参数类型"""
        from core.strategies.configurable.strategy_config import ParameterType
        
        assert ParameterType.INT.value == "int"
        assert ParameterType.FLOAT.value == "float"
        assert ParameterType.BOOL.value == "bool"
        assert ParameterType.STRING.value == "string"
        assert ParameterType.SELECT.value == "select"


class TestIndicatorType:
    """指标类型枚举测试"""
    
    def test_indicator_types(self):
        """测试指标类型"""
        from core.strategies.configurable.strategy_config import IndicatorType
        
        assert IndicatorType.MA.value == "ma"
        assert IndicatorType.EMA.value == "ema"
        assert IndicatorType.RSI.value == "rsi"
        assert IndicatorType.MACD.value == "macd"


class TestActionType:
    """交易动作枚举测试"""
    
    def test_action_types(self):
        """测试动作类型"""
        from core.strategies.configurable.strategy_config import ActionType
        
        assert ActionType.BUY.value == "buy"
        assert ActionType.SELL.value == "sell"
        assert ActionType.HOLD.value == "hold"


class TestParameterConfig:
    """参数配置测试"""
    
    def test_parameter_config_basic(self):
        """测试基本参数配置"""
        from core.strategies.configurable.strategy_config import ParameterConfig, ParameterType
        
        param = ParameterConfig(
            name="window",
            type=ParameterType.INT,
            default=20
        )
        
        assert param.name == "window"
        assert param.type == ParameterType.INT
        assert param.default == 20
    
    def test_parameter_config_with_string_type(self):
        """测试字符串类型转换"""
        from core.strategies.configurable.strategy_config import ParameterConfig, ParameterType
        
        param = ParameterConfig(
            name="window",
            type="int",
            default=20
        )
        
        assert param.type == ParameterType.INT
    
    def test_parameter_config_with_range(self):
        """测试带范围的参数"""
        from core.strategies.configurable.strategy_config import ParameterConfig, ParameterType
        
        param = ParameterConfig(
            name="window",
            type=ParameterType.INT,
            default=20,
            min=5,
            max=100,
            step=5
        )
        
        assert param.min == 5
        assert param.max == 100
        assert param.step == 5
    
    def test_parameter_config_with_options(self):
        """测试带选项的参数"""
        from core.strategies.configurable.strategy_config import ParameterConfig, ParameterType
        
        param = ParameterConfig(
            name="market",
            type=ParameterType.SELECT,
            default="SZ",
            options=[
                {"value": "SZ", "label": "深圳"},
                {"value": "SH", "label": "上海"}
            ]
        )
        
        assert len(param.options) == 2


class TestIndicatorConfig:
    """指标配置测试"""
    
    def test_indicator_config_basic(self):
        """测试基本指标配置"""
        from core.strategies.configurable.strategy_config import IndicatorConfig, IndicatorType
        
        indicator = IndicatorConfig(
            name="ma20",
            type=IndicatorType.MA,
            params={"column": "close", "window": 20}
        )
        
        assert indicator.name == "ma20"
        assert indicator.type == IndicatorType.MA
        assert indicator.params["window"] == 20
    
    def test_indicator_config_with_string_type(self):
        """测试字符串类型转换"""
        from core.strategies.configurable.strategy_config import IndicatorConfig, IndicatorType
        
        indicator = IndicatorConfig(
            name="rsi14",
            type="rsi"
        )
        
        assert indicator.type == IndicatorType.RSI


class TestStrategyConfigLoader:
    """策略配置加载器测试"""
    
    def test_loader_init(self):
        """测试加载器初始化"""
        from core.strategies.configurable.config_loader import StrategyConfigLoader
        
        loader = StrategyConfigLoader()
        
        assert loader.config_dir is not None
    
    def test_loader_with_custom_dir(self):
        """测试自定义目录"""
        from core.strategies.configurable.config_loader import StrategyConfigLoader
        from pathlib import Path
        
        loader = StrategyConfigLoader(config_dir="/custom/path")
        
        assert loader.config_dir == Path("/custom/path")
    
    def test_load_from_dict(self):
        """测试从字典加载"""
        from core.strategies.configurable.config_loader import StrategyConfigLoader
        
        loader = StrategyConfigLoader()
        
        config_data = {
            "strategy_id": "test_strategy",
            "name": "测试策略",
            "version": "1.0.0",
            "description": "测试策略描述"
        }
        
        config = loader.load_from_dict(config_data)
        
        assert config.strategy_id == "test_strategy"
        assert config.name == "测试策略"
    
    def test_load_file_not_found(self):
        """测试文件不存在"""
        from core.strategies.configurable.config_loader import StrategyConfigLoader
        
        loader = StrategyConfigLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent.yaml")


class TestStrategyConfig:
    """策略配置测试"""
    
    def test_strategy_config_basic(self):
        """测试基本策略配置"""
        from core.strategies.configurable.strategy_config import StrategyConfig
        
        config = StrategyConfig(
            strategy_id="test",
            name="测试策略",
            version="1.0.0"
        )
        
        assert config.strategy_id == "test"
        assert config.name == "测试策略"
        assert config.version == "1.0.0"
    
    def test_strategy_config_with_parameters(self):
        """测试带参数的策略配置"""
        from core.strategies.configurable.strategy_config import StrategyConfig, ParameterConfig, ParameterType
        
        config = StrategyConfig(
            strategy_id="test",
            name="测试策略",
            version="1.0.0",
            parameters=[
                ParameterConfig(
                    name="window",
                    type=ParameterType.INT,
                    default=20
                )
            ]
        )
        
        assert len(config.parameters) == 1
        assert config.parameters[0].name == "window"
    
    def test_strategy_config_with_indicators(self):
        """测试带指标的策略配置"""
        from core.strategies.configurable.strategy_config import StrategyConfig, IndicatorConfig, IndicatorType
        
        config = StrategyConfig(
            strategy_id="test",
            name="测试策略",
            version="1.0.0",
            indicators=[
                IndicatorConfig(
                    name="ma20",
                    type=IndicatorType.MA,
                    params={"window": 20}
                )
            ]
        )
        
        assert len(config.indicators) == 1
        assert config.indicators[0].name == "ma20"
