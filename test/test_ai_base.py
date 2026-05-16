"""
core/strategies/templates/ai_base.py AI策略基类测试

测试内容：
1. AIStrategyConfig 配置
2. AIStrategyBase 基类
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass


class TestAIStrategyConfig:
    """AI策略配置测试"""
    
    def test_config_init_default(self):
        """测试默认初始化"""
        from core.strategies.templates.ai_base import AIStrategyConfig
        
        config = AIStrategyConfig()
        
        assert config.params == {}
    
    def test_config_init_with_params(self):
        """测试带参数初始化"""
        from core.strategies.templates.ai_base import AIStrategyConfig
        
        config = AIStrategyConfig(params={
            "rsi_period": 14,
            "rsi_threshold": 30
        })
        
        assert config.params["rsi_period"] == 14
        assert config.params["rsi_threshold"] == 30
    
    def test_config_post_init_ensures_dict(self):
        """测试确保 params 是字典"""
        from core.strategies.templates.ai_base import AIStrategyConfig
        
        config = AIStrategyConfig(params=None)
        
        assert config.params == {}


class TestAIStrategyBase:
    """AI策略基类测试"""
    
    def test_ai_strategy_base_has_get_required_indicators(self):
        """测试是否有 get_required_indicators 方法"""
        from core.strategies.templates.ai_base import AIStrategyBase
        
        assert hasattr(AIStrategyBase, 'get_required_indicators')
    
    def test_ai_strategy_base_has_generate_signals(self):
        """测试是否有 generate_signals 方法"""
        from core.strategies.templates.ai_base import AIStrategyBase
        
        assert hasattr(AIStrategyBase, 'generate_signals')
    
    def test_ai_strategy_base_has_holding_state(self):
        """测试是否有 holding_state 属性"""
        from core.strategies.templates.ai_base import AIStrategyBase, AIStrategyConfig
        
        class TestAIStrategy(AIStrategyBase):
            def __init__(self, config: AIStrategyConfig):
                super().__init__(config)
            
            def get_required_indicators(self):
                return []
            
            def _generate_signals_impl(self, current_date, stock_pool):
                return {}
        
        config = AIStrategyConfig()
        strategy = TestAIStrategy(config)
        
        assert hasattr(strategy, 'holding_state')
        assert isinstance(strategy.holding_state, dict)
    
    def test_ai_strategy_base_config(self):
        """测试配置属性"""
        from core.strategies.templates.ai_base import AIStrategyBase, AIStrategyConfig
        
        class TestAIStrategy(AIStrategyBase):
            def __init__(self, config: AIStrategyConfig):
                super().__init__(config)
            
            def get_required_indicators(self):
                return []
            
            def _generate_signals_impl(self, current_date, stock_pool):
                return {}
        
        config = AIStrategyConfig(params={"test": 123})
        strategy = TestAIStrategy(config)
        
        assert strategy.config.params["test"] == 123
