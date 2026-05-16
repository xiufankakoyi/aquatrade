"""
core/portfolio/report_generator.py 报告生成器测试

测试内容：
1. ReportGenerator 初始化
2. 每日报告生成
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestReportGeneratorInit:
    """报告生成器初始化测试"""
    
    def test_init_default(self):
        """测试默认初始化"""
        from core.portfolio.report_generator import ReportGenerator
        
        with patch('core.portfolio.report_generator.PositionManager'):
            with patch('core.portfolio.report_generator.SignalEngine'):
                generator = ReportGenerator()
                
                assert generator.position_manager is not None
                assert generator.signal_engine is not None
    
    def test_init_with_custom_managers(self):
        """测试自定义管理器初始化"""
        from core.portfolio.report_generator import ReportGenerator
        
        mock_pm = Mock()
        mock_se = Mock()
        
        generator = ReportGenerator(
            position_manager=mock_pm,
            signal_engine=mock_se
        )
        
        assert generator.position_manager == mock_pm
        assert generator.signal_engine == mock_se
    
    def test_init_with_feishu(self):
        """测试飞书初始化"""
        from core.portfolio.report_generator import ReportGenerator
        
        with patch('core.portfolio.report_generator.PositionManager'):
            with patch('core.portfolio.report_generator.SignalEngine'):
                with patch('core.portfolio.report_generator.FeishuPush') as mock_feishu:
                    generator = ReportGenerator(feishu_webhook="https://test.webhook")
                    
                    mock_feishu.assert_called_once_with("https://test.webhook")


class TestReportGeneratorMethods:
    """报告生成器方法测试"""
    
    def test_get_market_summary(self):
        """测试大盘概览"""
        from core.portfolio.report_generator import ReportGenerator
        
        with patch('core.portfolio.report_generator.PositionManager'):
            with patch('core.portfolio.report_generator.SignalEngine'):
                generator = ReportGenerator()
                
                result = generator._get_market_summary()
                
                assert isinstance(result, list)


class TestReportGeneratorDataStructures:
    """报告生成器数据结构测试"""
    
    def test_position_data_structure(self):
        """测试持仓数据结构"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            shares=1000,
            current_price=11.0
        )
        
        assert pos.stock_code == "000001.SZ"
        assert pos.buy_price == 10.0
        assert pos.shares == 1000
    
    def test_signal_data_structure(self):
        """测试信号数据结构"""
        from core.portfolio.signal_engine import Signal
        
        signal = Signal(
            stock_code="000001.SZ",
            stock_name="平安银行",
            signal_date="2024-01-15",
            signal_type="buy",
            signal_name="MA金叉"
        )
        
        assert signal.stock_code == "000001.SZ"
        assert signal.signal_type == "buy"
