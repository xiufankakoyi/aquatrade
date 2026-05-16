"""
core/strategies/trend_follow_v3.py 中长期趋势策略V3测试

测试内容：
1. TrendFollowV3Config 配置
2. TrendFollowStrategyV3 初始化
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestTrendFollowV3Config:
    """中长期趋势V3配置测试"""
    
    def test_config_default_values(self):
        """测试默认配置值"""
        from core.strategies.trend_follow_v3 import TrendFollowV3Config
        
        config = TrendFollowV3Config()
        
        assert config.bias_threshold_high == 0.10
        assert config.bias_threshold_extreme == 0.15
        assert config.trend_ma_fast == 5
        assert config.trend_ma_slow == 10
        assert config.trend_ma_base == 20
    
    def test_config_stop_loss(self):
        """测试止损配置"""
        from core.strategies.trend_follow_v3 import TrendFollowV3Config
        
        config = TrendFollowV3Config()
        
        assert config.stop_loss_pct == 0.10
        assert config.trailing_stop_pct == 0.08
        assert config.max_hold_days == 120
    
    def test_config_position(self):
        """测试仓位配置"""
        from core.strategies.trend_follow_v3 import TrendFollowV3Config
        
        config = TrendFollowV3Config()
        
        assert config.position_ratio == 0.25
        assert config.max_stocks_per_day == 2
        assert config.max_positions == 6
    
    def test_config_market_cap(self):
        """测试市值配置"""
        from core.strategies.trend_follow_v3 import TrendFollowV3Config
        
        config = TrendFollowV3Config()
        
        assert config.market_cap_min == 20 * 10000
        assert config.market_cap_max == 5000 * 10000


class TestTrendFollowStrategyV3Init:
    """中长期趋势V3策略初始化测试"""
    
    def test_strategy_init_default(self):
        """测试默认初始化"""
        from core.strategies.trend_follow_v3 import TrendFollowStrategyV3
        
        strategy = TrendFollowStrategyV3()
        
        assert strategy.strategy_id == "trend_follow_v3"
        assert strategy.strategy_name == "中长期趋势跟踪策略V3(向量化)"
    
    def test_strategy_init_with_kwargs(self):
        """测试带参数初始化"""
        from core.strategies.trend_follow_v3 import TrendFollowStrategyV3
        
        strategy = TrendFollowStrategyV3(position_ratio=0.3)
        
        assert strategy.config.position_ratio == 0.3
    
    def test_strategy_needs_today_pool(self):
        """测试不需要当日股票池"""
        from core.strategies.trend_follow_v3 import TrendFollowStrategyV3
        
        strategy = TrendFollowStrategyV3()
        
        assert strategy.needs_today_pool is False
    
    def test_strategy_has_generate_signals(self):
        """测试是否有信号生成方法"""
        from core.strategies.trend_follow_v3 import TrendFollowStrategyV3
        
        strategy = TrendFollowStrategyV3()
        
        assert hasattr(strategy, 'generate_signals_vectorized')
