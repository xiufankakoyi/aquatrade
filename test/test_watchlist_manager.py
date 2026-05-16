"""
core/portfolio/watchlist_manager.py 自选股管理测试

测试内容：
1. WatchItem 数据结构
2. MonitorCondition 数据结构
3. 支持的监控条件
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestSupportedConditions:
    """支持的监控条件测试"""
    
    def test_price_conditions(self):
        """测试价格条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'price' in SUPPORTED_CONDITIONS
        price_conditions = SUPPORTED_CONDITIONS['price']['conditions']
        
        condition_keys = [c['key'] for c in price_conditions]
        assert 'price_above' in condition_keys
        assert 'price_below' in condition_keys
    
    def test_ma_conditions(self):
        """测试均线条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'ma' in SUPPORTED_CONDITIONS
        ma_conditions = SUPPORTED_CONDITIONS['ma']['conditions']
        
        condition_keys = [c['key'] for c in ma_conditions]
        assert 'ma5_break_up' in condition_keys
        assert 'ma_golden_cross' in condition_keys
    
    def test_macd_conditions(self):
        """测试MACD条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'macd' in SUPPORTED_CONDITIONS
        macd_conditions = SUPPORTED_CONDITIONS['macd']['conditions']
        
        condition_keys = [c['key'] for c in macd_conditions]
        assert 'macd_golden_cross' in condition_keys
        assert 'macd_death_cross' in condition_keys
    
    def test_rsi_conditions(self):
        """测试RSI条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'rsi' in SUPPORTED_CONDITIONS
        rsi_conditions = SUPPORTED_CONDITIONS['rsi']['conditions']
        
        condition_keys = [c['key'] for c in rsi_conditions]
        assert 'rsi_oversold' in condition_keys
        assert 'rsi_overbought' in condition_keys
    
    def test_kdj_conditions(self):
        """测试KDJ条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'kdj' in SUPPORTED_CONDITIONS
        kdj_conditions = SUPPORTED_CONDITIONS['kdj']['conditions']
        
        condition_keys = [c['key'] for c in kdj_conditions]
        assert 'kdj_golden_cross' in condition_keys
    
    def test_boll_conditions(self):
        """测试布林带条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'boll' in SUPPORTED_CONDITIONS
        boll_conditions = SUPPORTED_CONDITIONS['boll']['conditions']
        
        condition_keys = [c['key'] for c in boll_conditions]
        assert 'boll_break_upper' in condition_keys
    
    def test_volume_conditions(self):
        """测试成交量条件"""
        from core.portfolio.watchlist_manager import SUPPORTED_CONDITIONS
        
        assert 'volume' in SUPPORTED_CONDITIONS
        volume_conditions = SUPPORTED_CONDITIONS['volume']['conditions']
        
        condition_keys = [c['key'] for c in volume_conditions]
        assert 'volume_surge' in condition_keys


class TestMonitorCondition:
    """MonitorCondition 数据结构测试"""
    
    def test_monitor_condition_creation(self):
        """测试创建监控条件"""
        from core.portfolio.watchlist_manager import MonitorCondition
        
        condition = MonitorCondition(
            key="price_above",
            category="price",
            params={"target_price": 15.0}
        )
        
        assert condition.key == "price_above"
        assert condition.category == "price"
        assert condition.params["target_price"] == 15.0
    
    def test_monitor_condition_default_values(self):
        """测试默认值"""
        from core.portfolio.watchlist_manager import MonitorCondition
        
        condition = MonitorCondition(
            key="ma5_break_up",
            category="ma"
        )
        
        assert condition.params == {}
        assert condition.enabled is True


class TestWatchItem:
    """WatchItem 数据结构测试"""
    
    def test_watch_item_creation(self):
        """测试创建监控项"""
        from core.portfolio.watchlist_manager import WatchItem
        
        item = WatchItem(
            stock_code="000001.SZ",
            stock_name="平安银行"
        )
        
        assert item.stock_code == "000001.SZ"
        assert item.stock_name == "平安银行"
    
    def test_watch_item_with_conditions(self):
        """测试带条件的监控项"""
        from core.portfolio.watchlist_manager import WatchItem
        
        item = WatchItem(
            stock_code="000001.SZ",
            stock_name="平安银行",
            conditions=[{"key": "price_above", "params": {"target_price": 15.0}}]
        )
        
        assert len(item.conditions) == 1
        assert item.conditions[0]["key"] == "price_above"
    
    def test_watch_item_with_target_prices(self):
        """测试带目标价的监控项"""
        from core.portfolio.watchlist_manager import WatchItem
        
        item = WatchItem(
            stock_code="000001.SZ",
            stock_name="平安银行",
            buy_target_price=10.0,
            sell_target_price=15.0
        )
        
        assert item.buy_target_price == 10.0
        assert item.sell_target_price == 15.0
    
    def test_watch_item_with_tags(self):
        """测试带标签的监控项"""
        from core.portfolio.watchlist_manager import WatchItem
        
        item = WatchItem(
            stock_code="000001.SZ",
            stock_name="平安银行",
            tags=["银行", "蓝筹"]
        )
        
        assert len(item.tags) == 2
        assert "银行" in item.tags


class TestWatchlistManagerMethods:
    """WatchlistManager 方法测试"""
    
    def test_get_next_id_empty(self):
        """测试空列表获取下一个ID"""
        from core.portfolio.watchlist_manager import WatchlistManager
        
        with patch.object(WatchlistManager, '__init__', lambda x: None):
            manager = WatchlistManager()
            manager._get_next_id = WatchlistManager._get_next_id.__get__(manager)
            
            df = pd.DataFrame()
            
            result = manager._get_next_id(df)
            
            assert result == 1
    
    def test_get_next_id_with_data(self):
        """测试有数据时获取下一个ID"""
        from core.portfolio.watchlist_manager import WatchlistManager
        
        with patch.object(WatchlistManager, '__init__', lambda x: None):
            manager = WatchlistManager()
            manager._get_next_id = WatchlistManager._get_next_id.__get__(manager)
            
            df = pd.DataFrame({'id': [1, 2, 3]})
            
            result = manager._get_next_id(df)
            
            assert result == 4
    
    def test_get_next_id_no_id_column(self):
        """测试无ID列时获取下一个ID"""
        from core.portfolio.watchlist_manager import WatchlistManager
        
        with patch.object(WatchlistManager, '__init__', lambda x: None):
            manager = WatchlistManager()
            manager._get_next_id = WatchlistManager._get_next_id.__get__(manager)
            
            df = pd.DataFrame({'stock_code': ['000001.SZ']})
            
            result = manager._get_next_id(df)
            
            assert result == 1
