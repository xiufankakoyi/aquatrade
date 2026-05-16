"""
core/utils/strategy_runner.py 策略运行器测试

测试内容：
1. StrategyRunner 类初始化
2. 方法存在性验证
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestStrategyRunnerInit:
    """策略运行器初始化测试"""
    
    def test_init_with_strategy_and_engine(self):
        """测试带策略和引擎初始化"""
        from core.utils.strategy_runner import StrategyRunner
        
        mock_strategy = Mock()
        mock_engine = Mock()
        
        runner = StrategyRunner(mock_strategy, mock_engine)
        
        assert runner.strategy is mock_strategy
        assert runner.data_engine is mock_engine
    
    def test_init_creates_holding_state(self):
        """测试初始化创建持仓状态"""
        from core.utils.strategy_runner import StrategyRunner
        
        mock_strategy = Mock()
        del mock_strategy.holding_state
        mock_engine = Mock()
        
        runner = StrategyRunner(mock_strategy, mock_engine)
        
        assert hasattr(mock_strategy, 'holding_state')
        assert mock_strategy.holding_state == {}


class TestStrategyRunnerMethods:
    """策略运行器方法测试"""
    
    def test_has_on_bar(self):
        """测试是否有on_bar方法"""
        from core.utils.strategy_runner import StrategyRunner
        
        assert hasattr(StrategyRunner, 'on_bar')
    
    def test_has_update_holding_state(self):
        """测试是否有_update_holding_state方法"""
        from core.utils.strategy_runner import StrategyRunner
        
        assert hasattr(StrategyRunner, '_update_holding_state')
    
    def test_has_get_daily_snapshot(self):
        """测试是否有_get_daily_snapshot方法"""
        from core.utils.strategy_runner import StrategyRunner
        
        assert hasattr(StrategyRunner, '_get_daily_snapshot')
