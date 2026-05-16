"""
core/strategies/trend_follow_v1.py 中长期趋势策略测试

测试内容：
1. TrendFollowConfig 配置
2. TrendFollowStrategy 初始化
3. PARAM_SPEC 参数规范
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestTrendFollowConfigV1:
    """中长期趋势配置测试"""
    
    def test_config_default_values(self):
        """测试默认配置值"""
        from core.strategies.trend_follow_v1 import TrendFollowConfig
        
        config = TrendFollowConfig()
        
        assert config.bias_threshold_high == 0.12
        assert config.bias_threshold_extreme == 0.18
        assert config.trend_ma_fast == 5
        assert config.trend_ma_slow == 10
        assert config.trend_ma_base == 20
    
    def test_config_stop_loss(self):
        """测试止损配置"""
        from core.strategies.trend_follow_v1 import TrendFollowConfig
        
        config = TrendFollowConfig()
        
        assert config.stop_loss_pct == 0.08
        assert config.trailing_stop_pct == 0.05
        assert config.max_hold_days == 60
    
    def test_config_position(self):
        """测试仓位配置"""
        from core.strategies.trend_follow_v1 import TrendFollowConfig
        
        config = TrendFollowConfig()
        
        assert config.position_ratio == 0.2
        assert config.max_stocks_per_day == 3
    
    def test_config_bank_codes(self):
        """测试银行股列表"""
        from core.strategies.trend_follow_v1 import TrendFollowConfig
        
        config = TrendFollowConfig()
        
        assert isinstance(config.bank_codes, list)
        assert len(config.bank_codes) > 0


class TestTrendFollowStrategyV1Init:
    """中长期趋势策略初始化测试"""
    
    def test_strategy_init_default(self):
        """测试默认初始化"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        strategy = TrendFollowStrategy()
        
        assert strategy.strategy_id == "trend_follow_v1"
        assert strategy.strategy_name == "中长期趋势跟踪策略"
    
    def test_strategy_param_spec(self):
        """测试参数规范"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        assert hasattr(TrendFollowStrategy, 'PARAM_SPEC')
        assert isinstance(TrendFollowStrategy.PARAM_SPEC, list)
    
    def test_strategy_param_spec_keys(self):
        """测试参数规范键"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        keys = [spec['key'] for spec in TrendFollowStrategy.PARAM_SPEC]
        
        assert 'bias_threshold_high' in keys
        assert 'stop_loss_pct' in keys
        assert 'trailing_stop_pct' in keys
    
    def test_strategy_needs_today_pool(self):
        """测试需要当日股票池"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        strategy = TrendFollowStrategy()
        
        assert strategy.needs_today_pool is True


class TestTrendFollowStrategyV1Methods:
    """中长期趋势策略方法测试"""
    
    def test_has_generate_signals(self):
        """测试是否有信号生成方法"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        strategy = TrendFollowStrategy()
        
        assert hasattr(strategy, 'generate_signals')
    
    def test_has_get_param_spec(self):
        """测试是否有参数规范方法"""
        from core.strategies.trend_follow_v1 import TrendFollowStrategy
        
        assert hasattr(TrendFollowStrategy, 'get_param_spec')
