"""
core/portfolio/position_manager.py 持仓管理测试

测试内容：
1. 持仓数据结构
2. 持仓增删改查
3. 盈亏计算
4. 止损止盈检查
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestPosition:
    """持仓数据结构测试"""
    
    def test_position_creation(self):
        """测试持仓创建"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001",
            stock_name="平安银行",
            buy_price=10.0,
            shares=1000,
            cost=10000.0,
            buy_date="2025-01-01"
        )
        
        assert pos.stock_code == "000001"
        assert pos.stock_name == "平安银行"
        assert pos.buy_price == 10.0
        assert pos.shares == 1000
        assert pos.cost == 10000.0
        assert pos.is_active == True
    
    def test_position_with_stop_loss(self):
        """测试带止损的持仓"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001",
            stock_name="平安银行",
            buy_price=10.0,
            shares=1000,
            cost=10000.0,
            buy_date="2025-01-01",
            stop_loss=9.0,
            take_profit=12.0
        )
        
        assert pos.stop_loss == 9.0
        assert pos.take_profit == 12.0
    
    def test_position_default_values(self):
        """测试默认值"""
        from core.portfolio.position_manager import Position
        
        pos = Position()
        
        assert pos.stock_code == ""
        assert pos.buy_price == 0.0
        assert pos.shares == 0.0
        assert pos.is_active == True
        assert pos.stop_loss is None
        assert pos.take_profit is None


class TestPositionManagerCRUD:
    """持仓管理器 CRUD 测试"""
    
    @pytest.fixture
    def mock_manager(self):
        """创建 Mock 管理器"""
        from core.portfolio.position_manager import PositionManager
        
        with patch.object(PositionManager, 'library'):
            manager = PositionManager()
            manager._library = Mock()
            return manager
    
    def test_get_next_id_empty(self, mock_manager):
        """测试空表获取下一个 ID"""
        import pandas as pd
        
        df = pd.DataFrame()
        next_id = mock_manager._get_next_id(df)
        
        assert next_id == 1
    
    def test_get_next_id_with_data(self, mock_manager):
        """测试有数据时获取下一个 ID"""
        import pandas as pd
        
        df = pd.DataFrame({'id': [1, 2, 3]})
        next_id = mock_manager._get_next_id(df)
        
        assert next_id == 4
    
    def test_row_to_position(self, mock_manager):
        """测试行转换为 Position"""
        import pandas as pd
        
        row = pd.Series({
            'id': 1,
            'stock_code': '000001',
            'stock_name': '平安银行',
            'buy_price': 10.0,
            'shares': 1000.0,
            'cost': 10000.0,
            'buy_date': '2025-01-01',
            'stop_loss': 9.0,
            'take_profit': 12.0,
            'notes': '测试',
            'is_active': 1,
            'created_at': '2025-01-01 10:00:00',
            'updated_at': '2025-01-01 10:00:00'
        })
        
        pos = mock_manager._row_to_position(row)
        
        assert pos.id == 1
        assert pos.stock_code == '000001'
        assert pos.stock_name == '平安银行'
        assert pos.buy_price == 10.0
        assert pos.is_active == True


class TestPositionManagerAnalysis:
    """持仓分析测试"""
    
    @pytest.fixture
    def manager(self):
        """创建管理器"""
        from core.portfolio.position_manager import PositionManager, Position
        
        with patch.object(PositionManager, 'library'):
            manager = PositionManager()
            manager._library = Mock()
            return manager
    
    def test_calculate_analysis(self, manager):
        """测试持仓分析计算"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01"
            ),
            Position(
                stock_code="000002",
                stock_name="万科A",
                buy_price=20.0,
                shares=500,
                cost=10000.0,
                buy_date="2025-01-02"
            )
        ]
        
        price_data = {
            "000001": 11.0,
            "000002": 22.0
        }
        
        result = manager.calculate_analysis(positions, price_data)
        
        assert 'positions' in result
        assert 'summary' in result
        assert result['summary']['position_count'] == 2
        assert result['summary']['total_cost'] == 20000.0
    
    def test_calculate_analysis_profit(self, manager):
        """测试盈亏计算"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01"
            )
        ]
        
        price_data = {"000001": 12.0}
        
        result = manager.calculate_analysis(positions, price_data)
        
        assert result['summary']['total_profit_loss'] == 2000.0
        assert result['summary']['total_profit_loss_pct'] == 20.0
    
    def test_calculate_analysis_loss(self, manager):
        """测试亏损计算"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01"
            )
        ]
        
        price_data = {"000001": 8.0}
        
        result = manager.calculate_analysis(positions, price_data)
        
        assert result['summary']['total_profit_loss'] == -2000.0
        assert result['summary']['total_profit_loss_pct'] == -20.0
    
    def test_calculate_analysis_weight(self, manager):
        """测试权重计算"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01"
            ),
            Position(
                stock_code="000002",
                stock_name="万科A",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-02"
            )
        ]
        
        price_data = {
            "000001": 10.0,
            "000002": 10.0
        }
        
        result = manager.calculate_analysis(positions, price_data)
        
        assert result['positions'][0]['weight'] == 50.0
        assert result['positions'][1]['weight'] == 50.0


class TestStopLossTakeProfit:
    """止损止盈测试"""
    
    @pytest.fixture
    def manager(self):
        """创建管理器"""
        from core.portfolio.position_manager import PositionManager
        
        with patch.object(PositionManager, 'library'):
            manager = PositionManager()
            manager._library = Mock()
            return manager
    
    def test_stop_loss_trigger(self, manager):
        """测试止损触发"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01",
                stop_loss=9.0
            )
        ]
        
        price_data = {"000001": 8.5}
        
        alerts = manager.check_stop_loss_take_profit(positions, price_data)
        
        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'stop_loss'
        assert alerts[0]['stock_code'] == '000001'
    
    def test_stop_loss_not_trigger(self, manager):
        """测试止损未触发"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01",
                stop_loss=9.0
            )
        ]
        
        price_data = {"000001": 9.5}
        
        alerts = manager.check_stop_loss_take_profit(positions, price_data)
        
        assert len(alerts) == 0
    
    def test_take_profit_trigger(self, manager):
        """测试止盈触发"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01",
                take_profit=12.0
            )
        ]
        
        price_data = {"000001": 13.0}
        
        alerts = manager.check_stop_loss_take_profit(positions, price_data)
        
        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'take_profit'
    
    def test_both_trigger(self, manager):
        """测试同时触发止损止盈"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                buy_price=10.0,
                shares=1000,
                cost=10000.0,
                buy_date="2025-01-01",
                stop_loss=9.0,
                take_profit=12.0
            )
        ]
        
        price_data = {"000001": 8.0}
        
        alerts = manager.check_stop_loss_take_profit(positions, price_data)
        
        assert len(alerts) == 1
        assert alerts[0]['alert_type'] == 'stop_loss'


class TestIndustryDistribution:
    """行业分布测试"""
    
    @pytest.fixture
    def manager(self):
        """创建管理器"""
        from core.portfolio.position_manager import PositionManager
        
        with patch.object(PositionManager, 'library'):
            manager = PositionManager()
            manager._library = Mock()
            return manager
    
    def test_get_industry_distribution(self, manager):
        """测试行业分布计算"""
        from core.portfolio.position_manager import Position
        
        positions = [
            Position(
                stock_code="000001",
                stock_name="平安银行",
                market_value=10000.0
            ),
            Position(
                stock_code="000002",
                stock_name="万科A",
                market_value=10000.0
            )
        ]
        
        with patch.object(manager, '_get_industry_info', return_value={
            '000001': '银行',
            '000002': '房地产'
        }):
            distribution = manager.get_industry_distribution(positions)
        
        assert '银行' in distribution
        assert '房地产' in distribution
    
    def test_get_industry_distribution_empty(self, manager):
        """测试空持仓行业分布"""
        distribution = manager.get_industry_distribution([])
        
        assert distribution == {}
    
    def test_get_industry_distribution_from_dict(self, manager):
        """测试从字典计算行业分布"""
        positions = [
            {'stock_code': '000001', 'market_value': 10000.0},
            {'stock_code': '000002', 'market_value': 10000.0}
        ]
        
        with patch.object(manager, '_get_industry_info', return_value={
            '000001': '银行',
            '000002': '银行'
        }):
            distribution = manager.get_industry_distribution_from_dict(positions)
        
        assert distribution.get('银行') == 100.0
