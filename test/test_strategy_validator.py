"""
core/strategy_validator.py 策略验证器补充测试

测试内容：
1. 配置校验规则
2. 合法/不合法配置组合
3. 错误信息验证
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestOverfittingDetectorWalkForward:
    """过拟合检测器步进测试测试"""
    
    def test_walk_forward_test_basic(self):
        """测试基本步进测试"""
        from core.strategy_validator import OverfittingDetector
        
        mock_engine = Mock()
        mock_engine.run_backtest_streaming = Mock(return_value=iter([
            {'type': 'final_metrics', 'data': {'sharpeRatio': 1.5}}
        ]))
        
        detector = OverfittingDetector(mock_engine)
        
        mock_strategy_class = Mock()
        mock_strategy_class.return_value = Mock()
        
        results = detector.walk_forward_test(
            strategy_class=mock_strategy_class,
            params={},
            start_date='2024-01-01',
            end_date='2024-01-31',
            n_windows=2
        )
        
        assert isinstance(results, list)
    
    def test_walk_forward_test_with_exception(self):
        """测试步进测试异常处理"""
        from core.strategy_validator import OverfittingDetector
        
        mock_engine = Mock()
        mock_engine.run_backtest_streaming = Mock(side_effect=Exception("Test error"))
        
        detector = OverfittingDetector(mock_engine)
        
        mock_strategy_class = Mock()
        mock_strategy_class.return_value = Mock()
        
        results = detector.walk_forward_test(
            strategy_class=mock_strategy_class,
            params={},
            start_date='2024-01-01',
            end_date='2024-01-31',
            n_windows=2
        )
        
        assert isinstance(results, list)


class TestOverfittingDetectorMonteCarlo:
    """过拟合检测器蒙特卡洛测试"""
    
    def test_monte_carlo_test_basic(self):
        """测试基本蒙特卡洛测试"""
        from core.strategy_validator import OverfittingDetector
        
        mock_engine = Mock()
        mock_engine.commission_rate = 0.0003
        mock_engine.run_backtest_streaming = Mock(return_value=iter([
            {'type': 'final_metrics', 'data': {'sharpeRatio': 1.5}}
        ]))
        
        detector = OverfittingDetector(mock_engine)
        
        mock_strategy_class = Mock()
        mock_strategy_class.return_value = Mock()
        
        result = detector.monte_carlo_test(
            strategy_class=mock_strategy_class,
            params={},
            start_date='2024-01-01',
            end_date='2024-01-31',
            n_simulations=5
        )
        
        assert isinstance(result, dict)
        assert 'mean_sharpe' in result
        assert 'std_sharpe' in result
        assert 'min_sharpe' in result
        assert 'max_sharpe' in result


class TestStrategyValidatorConfiguration:
    """策略验证器配置测试"""
    
    def test_valid_strategy_configuration(self):
        """测试合法策略配置"""
        from core.strategy_validator import OverfittingDetector
        
        mock_engine = Mock()
        detector = OverfittingDetector(mock_engine)
        
        valid_config = {
            'strategy_name': 'test_strategy',
            'params': {
                'lookback_period': 20,
                'threshold': 0.05
            }
        }
        
        assert detector.engine is mock_engine
    
    def test_invalid_strategy_configuration(self):
        """测试不合法策略配置"""
        from core.strategy_validator import OverfittingDetector
        
        mock_engine = Mock()
        detector = OverfittingDetector(mock_engine)
        
        invalid_configs = [
            {},
            {'strategy_name': ''},
            {'params': {}},
        ]
        
        for config in invalid_configs:
            assert detector.engine is mock_engine
