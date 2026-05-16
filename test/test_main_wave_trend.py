"""
core/strategies/user/main_wave_trend.py 主升浪趋势策略测试

测试内容：
1. MainWaveConfig 配置
2. MainWaveTrendStrategy 初始化
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestMainWaveConfig:
    """主升浪配置测试"""
    
    def test_config_default_values(self):
        """测试默认配置值"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.trend_ma_fast == 5
        assert config.trend_ma_mid == 10
        assert config.trend_ma_slow == 20
    
    def test_config_breakout_params(self):
        """测试突破参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.breakout_days == 5
        assert config.breakout_pct == 0.08
        assert config.consecutive_up_days == 3
    
    def test_config_pullback_params(self):
        """测试回踩参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.pullback_to_ma5_max == 0.03
        assert config.pullback_to_ma10_max == 0.03
    
    def test_config_bias_params(self):
        """测试乖离率参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.bias_normal_max == 0.05
        assert config.bias_high_max == 0.10
        assert config.bias_extreme_max == 0.15
    
    def test_config_volume_params(self):
        """测试量能参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.volume_ratio_min == 1.5
    
    def test_config_position_params(self):
        """测试仓位参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.position_ratio == 0.20
        assert config.max_positions == 5
        assert config.max_stocks_per_day == 2
    
    def test_config_stop_loss_params(self):
        """测试止损止盈参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.stop_loss_pct == 0.08
        assert config.trailing_stop_pct == 0.05
        assert config.take_profit_pct == 0.30
    
    def test_config_hold_days(self):
        """测试持仓周期"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.min_hold_days == 2
        assert config.max_hold_days == 60
    
    def test_config_stock_filter(self):
        """测试股票筛选参数"""
        from core.strategies.user.main_wave_trend import MainWaveConfig
        
        config = MainWaveConfig()
        
        assert config.min_list_days == 60
        assert config.market_cap_min == 30 * 10000
        assert config.market_cap_max == 2000 * 10000


class TestMainWaveTrendStrategyInit:
    """主升浪策略初始化测试"""
    
    def test_strategy_init_default(self):
        """测试默认初始化"""
        from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
        
        strategy = MainWaveTrendStrategy()
        
        assert strategy.strategy_id == "main_wave_trend"
        assert "主升浪" in strategy.strategy_name
    
    def test_strategy_init_with_kwargs(self):
        """测试带参数初始化"""
        from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
        
        strategy = MainWaveTrendStrategy(position_ratio=0.3)
        
        assert strategy.config.position_ratio == 0.3
    
    def test_strategy_needs_today_pool(self):
        """测试不需要当日股票池"""
        from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
        
        strategy = MainWaveTrendStrategy()
        
        assert strategy.needs_today_pool is False
    
    def test_strategy_has_generate_signals(self):
        """测试是否有信号生成方法"""
        from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
        
        strategy = MainWaveTrendStrategy()
        
        assert hasattr(strategy, 'generate_signals_vectorized')
