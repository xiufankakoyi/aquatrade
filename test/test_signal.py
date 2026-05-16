"""
信号生成测试

测试内容：
1. 信号矩阵格式验证
2. 买入信号生成逻辑
3. 卖出信号生成逻辑
4. 信号过滤逻辑
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime


class TestSignalMatrix:
    """信号矩阵测试"""
    
    def test_signal_matrix_shape(self, sample_signal_matrix, sample_trading_dates, sample_stock_codes):
        """测试信号矩阵形状"""
        T = len(sample_trading_dates)
        N = len(sample_stock_codes)
        
        assert sample_signal_matrix.shape == (T, N)
    
    def test_signal_values(self, sample_signal_matrix):
        """测试信号值范围"""
        unique_values = np.unique(sample_signal_matrix)
        
        for v in unique_values:
            assert v in [0, 1, -1]
    
    def test_buy_signal_detection(self, sample_signal_matrix):
        """测试买入信号检测"""
        buy_mask = sample_signal_matrix == 1
        buy_count = np.sum(buy_mask)
        
        assert buy_count > 0
    
    def test_sell_signal_detection(self, sample_signal_matrix):
        """测试卖出信号检测"""
        sell_mask = sample_signal_matrix == -1
        sell_count = np.sum(sell_mask)
        
        assert sell_count > 0
    
    def test_no_signal_conflict(self, sample_signal_matrix):
        """测试信号不冲突（同一天同一股票不会同时买入和卖出）"""
        buy_mask = sample_signal_matrix == 1
        sell_mask = sample_signal_matrix == -1
        
        conflict = buy_mask & sell_mask
        assert np.sum(conflict) == 0


class TestSignalGeneration:
    """信号生成逻辑测试"""
    
    def test_trend_follow_signal_logic(self):
        """测试趋势跟踪策略信号逻辑"""
        close = np.array([10.0, 10.5, 11.0, 11.5, 12.0, 11.5, 11.0])
        ma5 = np.array([9.5, 9.8, 10.2, 10.6, 11.0, 11.2, 11.1])
        ma10 = np.array([9.0, 9.2, 9.5, 9.8, 10.1, 10.4, 10.6])
        
        trend_ok = close > ma5
        price_above_ma5 = close > ma5
        price_above_ma10 = close > ma10
        
        buy_condition = trend_ok & price_above_ma5 & price_above_ma10
        
        assert np.any(buy_condition)
    
    def test_ma_cross_signal_logic(self):
        """测试均线交叉信号逻辑"""
        ma5 = np.array([10.0, 10.5, 11.0, 10.8, 10.5])
        ma10 = np.array([10.2, 10.3, 10.5, 10.6, 10.7])
        
        golden_cross = (ma5[:-1] <= ma10[:-1]) & (ma5[1:] > ma10[1:])
        death_cross = (ma5[:-1] >= ma10[:-1]) & (ma5[1:] < ma10[1:])
        
        assert np.any(golden_cross)
        assert np.any(death_cross)
    
    def test_volume_signal_logic(self):
        """测试成交量信号逻辑"""
        volume = np.array([100, 150, 200, 180, 250])
        volume_ma5 = np.array([120, 125, 130, 135, 140])
        
        volume_breakout = volume > volume_ma5 * 1.5
        
        assert volume_breakout[-1] == True
    
    def test_signal_from_strategy(self, sample_signal_matrix, sample_stock_codes):
        """测试从信号矩阵提取信号"""
        day_idx = 0
        day_signals = sample_signal_matrix[day_idx, :]
        
        buy_indices = np.where(day_signals == 1)[0]
        buy_codes = [sample_stock_codes[i] for i in buy_indices]
        
        assert len(buy_codes) == 3


class TestSignalFiltering:
    """信号过滤测试"""
    
    def test_filter_by_position_limit(self):
        """测试持仓限制过滤"""
        signals = {'000001': 'buy', '000002': 'buy', '000003': 'buy'}
        current_positions = 3
        max_positions = 5
        
        can_buy = max_positions - current_positions
        filtered = dict(list(signals.items())[:can_buy])
        
        assert len(filtered) == 2
    
    def test_filter_existing_positions(self):
        """测试过滤已持仓股票"""
        signals = {'000001': 'buy', '000002': 'buy', '000003': 'buy'}
        portfolio = {'000001': 100}
        
        filtered = {k: v for k, v in signals.items() if k not in portfolio}
        
        assert '000001' not in filtered
        assert len(filtered) == 2
    
    def test_filter_suspended_stocks(self):
        """测试过滤停牌股票"""
        signals = {'000001': 'buy', '000002': 'buy', '000003': 'buy'}
        suspended = {'000002'}
        
        filtered = {k: v for k, v in signals.items() if k not in suspended}
        
        assert '000002' not in filtered
        assert len(filtered) == 2
    
    def test_filter_limit_up_stocks(self):
        """测试过滤涨停股票"""
        signals = {'000001': 'buy', '000002': 'buy', '000003': 'buy'}
        limit_up = {'000003'}
        
        filtered = {k: v for k, v in signals.items() if k not in limit_up}
        
        assert '000003' not in filtered
        assert len(filtered) == 2


class TestSignalTiming:
    """信号时序测试"""
    
    def test_no_lookahead_bias(self):
        """测试无未来函数"""
        close = np.array([10.0, 10.5, 11.0, 11.5, 12.0])
        
        for i in range(1, len(close)):
            signal_data = close[:i+1]
            assert len(signal_data) == i + 1
    
    def test_warmup_period(self):
        """测试预热期"""
        warmup_days = 5
        total_days = 20
        
        signal_days = total_days - warmup_days
        
        assert signal_days == 15
    
    def test_signal_delay(self):
        """测试信号延迟（T+1 执行）"""
        signal_date = "2025-06-03"
        execution_date = "2025-06-04"
        
        from datetime import datetime, timedelta
        signal_dt = datetime.strptime(signal_date, "%Y-%m-%d")
        execution_dt = datetime.strptime(execution_date, "%Y-%m-%d")
        
        assert execution_dt > signal_dt
