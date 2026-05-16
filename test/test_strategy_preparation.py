"""
core/utils/strategy_preparation.py 策略执行准备测试

测试内容：
1. prepare_strategy_execution 函数
2. 策略指标需求检查
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestPrepareStrategyExecution:
    """策略执行准备测试"""
    
    def test_prepare_strategy_execution_no_requirements(self):
        """测试无指标需求的策略"""
        from core.utils.strategy_preparation import prepare_strategy_execution
        
        mock_strategy = Mock()
        mock_strategy.name = "test_strategy"
        mock_data_engine = Mock()
        
        result = prepare_strategy_execution(
            strategy=mock_strategy,
            raw_data_engine=mock_data_engine,
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert result is None
    
    def test_prepare_strategy_execution_with_requirements(self):
        """测试有指标需求的策略"""
        from core.utils.strategy_preparation import prepare_strategy_execution
        
        mock_strategy = Mock()
        mock_strategy.name = "test_strategy"
        mock_strategy.get_required_indicators = Mock(return_value=[
            {'name': 'ma5', 'type': 'ma', 'period': 5},
            {'name': 'ma10', 'type': 'ma', 'period': 10}
        ])
        
        mock_data_engine = Mock()
        
        result = prepare_strategy_execution(
            strategy=mock_strategy,
            raw_data_engine=mock_data_engine,
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert result is None
    
    def test_prepare_strategy_execution_invalid_requirements(self):
        """测试无效指标需求的策略"""
        from core.utils.strategy_preparation import prepare_strategy_execution
        
        mock_strategy = Mock()
        mock_strategy.name = "test_strategy"
        mock_strategy.get_required_indicators = Mock(return_value="invalid")
        
        mock_data_engine = Mock()
        
        result = prepare_strategy_execution(
            strategy=mock_strategy,
            raw_data_engine=mock_data_engine,
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        
        assert result is None
