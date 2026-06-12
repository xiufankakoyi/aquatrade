"""
core/portfolio/position_manager.py 持仓管理测试

测试内容：
1. Position 数据结构
2. PositionManager 持仓管理
3. 盈亏计算
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestPositionDataStructure:
    """Position 数据结构测试"""
    
    def test_position_default_values(self):
        """测试默认值"""
        from core.portfolio.position_manager import Position
        
        pos = Position()
        
        assert pos.id is None
        assert pos.stock_code == ""
        assert pos.shares == 0.0
        assert pos.cost == 0.0
        assert pos.is_active is True
    
    def test_position_with_values(self):
        """测试带值的初始化"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            id=1,
            stock_code="000001.SZ",
            stock_name="平安银行",
            buy_price=10.5,
            shares=1000,
            cost=10500.0,
            buy_date="2024-01-15"
        )
        
        assert pos.id == 1
        assert pos.stock_code == "000001.SZ"
        assert pos.buy_price == 10.5
        assert pos.shares == 1000
    
    def test_position_optional_fields(self):
        """测试可选字段"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            stop_loss=9.5,
            take_profit=12.0,
            notes="测试持仓"
        )
        
        assert pos.stop_loss == 9.5
        assert pos.take_profit == 12.0
        assert pos.notes == "测试持仓"
    
    def test_position_calculated_fields(self):
        """测试计算字段"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            shares=1000,
            current_price=11.0
        )
        
        pos.market_value = pos.shares * pos.current_price
        pos.profit_loss = pos.market_value - (pos.shares * pos.buy_price)
        pos.profit_loss_pct = pos.profit_loss / (pos.shares * pos.buy_price) * 100
        
        assert pos.market_value == 11000.0
        assert pos.profit_loss == 1000.0
        assert pos.profit_loss_pct == 10.0


class TestPositionManagerInit:
    """PositionManager 初始化测试"""

    def test_init(self):
        """测试初始化：使用 Parquet 存储路径，不再持有 _arctic/_library"""
        from core.portfolio.position_manager import PositionManager

        with patch('core.portfolio.position_manager.os.path.exists', return_value=False):
            with patch('core.portfolio.position_manager.os.makedirs'):
                manager = PositionManager()

                # 当前实现：使用 Parquet 文件，不再持有 _arctic/_library
                assert not hasattr(manager, "_arctic")
                assert not hasattr(manager, "_library")
                assert manager.parquet_path.endswith("portfolio_positions.parquet")


class TestPositionManagerOperations:
    """PositionManager 操作测试"""
    
    @pytest.fixture
    def mock_manager(self):
        """创建 Mock 管理器"""
        from core.portfolio.position_manager import PositionManager
        
        manager = PositionManager()
        manager._library = Mock()
        manager._library.list_symbols = Mock(return_value=[])
        
        return manager
    
    def test_get_next_id_empty(self, mock_manager):
        """测试空表获取下一个 ID"""
        df = pd.DataFrame()
        
        result = mock_manager._get_next_id(df)
        
        assert result == 1
    
    def test_get_next_id_with_data(self, mock_manager):
        """测试有数据时获取下一个 ID"""
        df = pd.DataFrame({'id': [1, 2, 3]})
        
        result = mock_manager._get_next_id(df)
        
        assert result == 4
    
    def test_get_next_id_no_id_column(self, mock_manager):
        """测试无 ID 列时获取下一个 ID"""
        df = pd.DataFrame({'stock_code': ['000001.SZ']})
        
        result = mock_manager._get_next_id(df)
        
        assert result == 1


class TestPositionManagerSaveLoad:
    """PositionManager 保存加载测试"""
    
    def test_save_positions_df_converts_bool(self):
        """测试保存时转换布尔类型为 0/1，写入 Parquet 文件"""
        from core.portfolio.position_manager import PositionManager
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            manager = PositionManager()
            manager.parquet_path = os.path.join(tmp, "positions.parquet")

            df = pd.DataFrame({
                'id': [1],
                'stock_code': ['000001.SZ'],
                'is_active': [True]
            })

            manager._save_positions_df(df)

            # 验证 Parquet 文件被写入，且 is_active 被规范化为 0/1
            assert os.path.exists(manager.parquet_path)
            saved_df = pd.read_parquet(manager.parquet_path)
            assert int(saved_df['is_active'].iloc[0]) == 1
    
    def test_get_positions_df_empty(self):
        """测试获取空持仓"""
        from core.portfolio.position_manager import PositionManager
        
        manager = PositionManager()
        mock_library = Mock()
        mock_library.list_symbols = Mock(return_value=[])
        
        manager._library = mock_library
        
        with patch('os.path.exists', return_value=False):
            result = manager._get_positions_df()
            
            assert result.empty


class TestPositionProfitCalculation:
    """持仓盈亏计算测试"""
    
    def test_profit_calculation_positive(self):
        """测试盈利计算"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            shares=1000,
            current_price=12.0
        )
        
        cost = pos.buy_price * pos.shares
        market_value = pos.current_price * pos.shares
        profit = market_value - cost
        profit_pct = profit / cost * 100
        
        assert profit == 2000.0
        assert profit_pct == 20.0
    
    def test_profit_calculation_negative(self):
        """测试亏损计算"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            shares=1000,
            current_price=8.0
        )
        
        cost = pos.buy_price * pos.shares
        market_value = pos.current_price * pos.shares
        profit = market_value - cost
        profit_pct = profit / cost * 100
        
        assert profit == -2000.0
        assert profit_pct == -20.0
    
    def test_profit_calculation_zero(self):
        """测试持平计算"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            shares=1000,
            current_price=10.0
        )
        
        cost = pos.buy_price * pos.shares
        market_value = pos.current_price * pos.shares
        profit = market_value - cost
        
        assert profit == 0.0


class TestPositionStopLossTakeProfit:
    """止损止盈测试"""
    
    def test_stop_loss_trigger(self):
        """测试止损触发"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            stop_loss=9.0,
            current_price=8.5
        )
        
        should_stop = pos.current_price <= pos.stop_loss
        
        assert should_stop is True
    
    def test_stop_loss_not_trigger(self):
        """测试止损未触发"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            stop_loss=9.0,
            current_price=9.5
        )
        
        should_stop = pos.current_price <= pos.stop_loss
        
        assert should_stop is False
    
    def test_take_profit_trigger(self):
        """测试止盈触发"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            take_profit=12.0,
            current_price=12.5
        )
        
        should_take = pos.current_price >= pos.take_profit
        
        assert should_take is True
    
    def test_take_profit_not_trigger(self):
        """测试止盈未触发"""
        from core.portfolio.position_manager import Position
        
        pos = Position(
            stock_code="000001.SZ",
            buy_price=10.0,
            take_profit=12.0,
            current_price=11.5
        )
        
        should_take = pos.current_price >= pos.take_profit
        
        assert should_take is False
