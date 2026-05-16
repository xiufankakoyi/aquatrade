"""
data_svc/storage/unified_reader.py 统一读取器测试

测试内容:
1. 读取器初始化
2. 单股票读取
3. 批量读取
4. 缓存管理
5. 数据查询

注意: 使用 LanceDB 作为底层存储
"""

import pytest
import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class TestLanceDBDataReaderInit:
    """LanceDB 读取器初始化测试"""
    
    def test_reader_creation_default(self):
        """测试默认初始化"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect') as mock_connect:
                mock_db = Mock()
                mock_connect.return_value = mock_db
                
                reader = LanceDBDataReader()
                
                assert reader.TABLE_NAME == "daily_ohlcv"
                assert reader._db is None
                assert reader._table is None
    
    def test_reader_creation_custom_path(self):
        """测试自定义路径初始化"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect') as mock_connect:
                mock_db = Mock()
                mock_connect.return_value = mock_db
                
                reader = LanceDBDataReader(db_path="/custom/path")
                
                assert reader.db_path == "/custom/path"


class TestLanceDBDataReaderCache:
    """LanceDB 读取器缓存测试"""
    
    def test_cache_key_generation(self):
        """测试缓存 key 生成"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                key1 = reader._make_cache_key(None, "2024-01-01", "2024-12-31")
                assert "all" in key1
                assert "2024-01-01" in key1
                assert "2024-12-31" in key1
                
                key2 = reader._make_cache_key("000001.SZ", "2024-01-01", "2024-12-31")
                assert "000001.SZ" in key2
                
                key3 = reader._make_cache_key(["000001.SZ", "000002.SZ"], "2024-01-01", "2024-12-31")
                assert "batch" in key3
    
    def test_clear_cache(self):
        """测试清除缓存"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                reader._memory_cache["test_key"] = pl.DataFrame({"a": [1, 2, 3]})
                reader._current_cache_size_mb = 1.0
                
                reader.clear_cache()
                
                assert len(reader._memory_cache) == 0
                assert reader._current_cache_size_mb == 0.0


class TestLanceDBDataReaderFilters:
    """LanceDB 读取器过滤条件测试"""
    
    def test_build_filters_date_range(self):
        """测试日期范围过滤条件"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                filters = reader._build_filters(None, "2024-01-01", "2024-12-31")
                
                assert len(filters) == 2
                assert "trade_date >= date '2024-01-01'" in filters
                assert "trade_date <= date '2024-12-31'" in filters
    
    def test_build_filters_single_symbol(self):
        """测试单股票过滤条件"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                filters = reader._build_filters("000001.SZ", None, None)
                
                assert len(filters) == 1
                assert "stock_code = '000001.SZ'" in filters
    
    def test_build_filters_multiple_symbols(self):
        """测试多股票过滤条件"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                filters = reader._build_filters(["000001.SZ", "000002.SZ"], None, None)
                
                assert len(filters) == 1
                assert "stock_code IN" in filters[0]
    
    def test_build_filters_combined(self):
        """测试组合过滤条件"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                filters = reader._build_filters("000001.SZ", "2024-01-01", "2024-12-31")
                
                assert len(filters) == 3


class TestLanceDBDataReaderStats:
    """LanceDB 读取器统计测试"""
    
    def test_get_stats(self):
        """测试获取统计信息"""
        from data_svc.storage.unified_reader import LanceDBDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader = LanceDBDataReader()
                
                reader._query_count = 10
                reader._cache_hits = 5
                
                stats = reader.get_stats()
                
                assert stats["query_count"] == 10
                assert stats["cache_hits"] == 5
                assert stats["cache_hit_rate"] == 0.5


class TestUnifiedDataReaderAlias:
    """测试向后兼容别名"""
    
    def test_unified_data_reader_alias(self):
        """测试 UnifiedDataReader 是 LanceDBDataReader 的别名"""
        from data_svc.storage.unified_reader import UnifiedDataReader, LanceDBDataReader
        
        assert UnifiedDataReader is LanceDBDataReader


class TestGetUnifiedReader:
    """测试获取读取器单例"""
    
    def test_get_lancedb_reader_singleton(self):
        """测试单例模式"""
        from data_svc.storage.unified_reader import get_lancedb_reader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                reader1 = get_lancedb_reader()
                reader2 = get_lancedb_reader()
                
                assert reader1 is reader2


class TestUnifiedDataReaderDateColumn:
    """统一读取器日期列测试"""
    
    @pytest.fixture
    def reader(self):
        """创建读取器实例"""
        from data_svc.storage.unified_reader import UnifiedDataReader
        
        with patch('data_svc.storage.unified_reader.LANCEDB_AVAILABLE', True):
            with patch('data_svc.storage.unified_reader.lancedb.connect'):
                return UnifiedDataReader()
    
    def test_get_date_column_trade_date(self, reader):
        """测试获取 trade_date 列"""
        df = pl.DataFrame({
            "trade_date": ["2024-01-01", "2024-01-02"],
            "close": [10.0, 11.0],
        })
        
        result = reader._get_date_column(df)
        
        assert result == "trade_date"
    
    def test_get_date_column_date(self, reader):
        """测试获取 date 列"""
        df = pl.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "close": [10.0, 11.0],
        })
        
        result = reader._get_date_column(df)
        
        assert result == "date"
    
    def test_get_date_column_not_found(self, reader):
        """测试日期列不存在"""
        df = pl.DataFrame({
            "close": [10.0, 11.0],
        })
        
        result = reader._get_date_column(df)
        
        assert result is None
