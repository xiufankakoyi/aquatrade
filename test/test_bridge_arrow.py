"""
data_svc/bridge/arrow_bridge.py Arrow 数据桥梁测试

测试内容：
1. 数据格式转换 (Pandas/Polars <-> Arrow)
2. Schema 验证
3. RecordBatch 流式处理
4. IPC 序列化/反序列化
5. 表操作 (合并、过滤、排序)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date
from unittest.mock import Mock, patch


class TestArrowBridgeInit:
    """Arrow Bridge 初始化测试"""
    
    def test_bridge_creation(self):
        """测试 Bridge 创建"""
        from data_svc.bridge.arrow_bridge import ArrowBridge, reset_arrow_bridge
        
        reset_arrow_bridge()
        
        bridge = ArrowBridge()
        
        assert bridge is not None
        assert bridge._buffer == []
        assert bridge._schema_cache == {}
    
    def test_get_arrow_bridge_singleton(self):
        """测试获取单例"""
        from data_svc.bridge.arrow_bridge import get_arrow_bridge, reset_arrow_bridge
        
        reset_arrow_bridge()
        
        bridge1 = get_arrow_bridge()
        bridge2 = get_arrow_bridge()
        
        assert bridge1 is bridge2
    
    def test_reset_arrow_bridge(self):
        """测试重置单例"""
        from data_svc.bridge.arrow_bridge import get_arrow_bridge, reset_arrow_bridge
        
        reset_arrow_bridge()
        
        bridge1 = get_arrow_bridge()
        reset_arrow_bridge()
        bridge2 = get_arrow_bridge()
        
        assert bridge1 is not bridge2


class TestArrowBridgeSchema:
    """Arrow Bridge Schema 测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_stock_daily_schema(self, bridge):
        """测试股票日线 Schema"""
        schema = bridge.STOCK_DAILY_SCHEMA
        
        assert "trade_date" in schema.names
        assert "stock_code" in schema.names
        assert "open" in schema.names
        assert "high" in schema.names
        assert "low" in schema.names
        assert "close" in schema.names
        assert "volume" in schema.names
    
    def test_tick_schema(self, bridge):
        """测试 Tick Schema"""
        schema = bridge.TICK_SCHEMA
        
        assert "timestamp" in schema.names
        assert "stock_code" in schema.names
        assert "price" in schema.names
        assert "volume" in schema.names
    
    def test_factor_schema(self, bridge):
        """测试因子 Schema"""
        schema = bridge.FACTOR_SCHEMA
        
        assert "trade_date" in schema.names
        assert "stock_code" in schema.names
        assert "rsi_14" in schema.names
        assert "macd_dif" in schema.names
    
    def test_get_schema_daily(self, bridge):
        """测试获取日线 Schema"""
        schema = bridge.get_schema("daily")
        
        assert schema == bridge.STOCK_DAILY_SCHEMA
    
    def test_get_schema_tick(self, bridge):
        """测试获取 Tick Schema"""
        schema = bridge.get_schema("tick")
        
        assert schema == bridge.TICK_SCHEMA
    
    def test_get_schema_factor(self, bridge):
        """测试获取因子 Schema"""
        schema = bridge.get_schema("factor")
        
        assert schema == bridge.FACTOR_SCHEMA
    
    def test_get_schema_unknown(self, bridge):
        """测试获取未知类型 Schema"""
        schema = bridge.get_schema("unknown")
        
        assert schema == bridge.STOCK_DAILY_SCHEMA


class TestArrowBridgePandasConversion:
    """Arrow Bridge Pandas 转换测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_from_pandas_empty(self, bridge):
        """测试空 DataFrame 转换"""
        df = pd.DataFrame()
        
        result = bridge.from_pandas(df)
        
        assert result.num_rows == 0
    
    def test_from_pandas_simple(self, bridge):
        """测试简单 DataFrame 转换"""
        df = pd.DataFrame({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.from_pandas(df)
        
        assert result.num_rows == 3
        assert 'a' in result.column_names
        assert 'b' in result.column_names
    
    def test_from_pandas_with_index(self, bridge):
        """测试带索引 DataFrame 转换"""
        df = pd.DataFrame({
            'value': [10, 20, 30],
        }, index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']))
        
        result = bridge.from_pandas(df, preserve_index=True)
        
        assert result.num_rows == 3
    
    def test_to_pandas(self, bridge):
        """测试转换为 Pandas"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.to_pandas(table)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
    
    def test_roundtrip_pandas(self, bridge):
        """测试 Pandas 往返转换"""
        df = pd.DataFrame({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
            'c': ['x', 'y', 'z'],
        })
        
        table = bridge.from_pandas(df)
        result = bridge.to_pandas(table)
        
        assert len(result) == 3
        assert list(result['a']) == [1, 2, 3]


class TestArrowBridgePolarsConversion:
    """Arrow Bridge Polars 转换测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_from_polars_empty(self, bridge):
        """测试空 Polars DataFrame 转换"""
        import polars as pl
        
        df = pl.DataFrame()
        
        result = bridge.from_polars(df)
        
        assert result.num_rows == 0
    
    def test_from_polars_simple(self, bridge):
        """测试简单 Polars DataFrame 转换"""
        import polars as pl
        
        df = pl.DataFrame({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.from_polars(df)
        
        assert result.num_rows == 3
        assert 'a' in result.column_names
        assert 'b' in result.column_names
    
    def test_to_polars(self, bridge):
        """测试转换为 Polars"""
        import pyarrow as pa
        import polars as pl
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.to_polars(table)
        
        assert isinstance(result, pl.DataFrame)
        assert result.height == 3
    
    def test_roundtrip_polars(self, bridge):
        """测试 Polars 往返转换"""
        import polars as pl
        
        df = pl.DataFrame({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
            'c': ['x', 'y', 'z'],
        })
        
        table = bridge.from_polars(df)
        result = bridge.to_polars(table)
        
        assert result.height == 3
        assert result['a'].to_list() == [1, 2, 3]


class TestArrowBridgeRecordBatch:
    """Arrow Bridge RecordBatch 测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_create_record_batch_stream_pandas(self, bridge):
        """测试从 Pandas 创建 RecordBatch 流"""
        df = pd.DataFrame({
            'a': list(range(100)),
            'b': list(range(100, 200)),
        })
        
        batches = list(bridge.create_record_batch_stream(df, batch_size=30))
        
        assert len(batches) == 4
    
    def test_create_record_batch_stream_polars(self, bridge):
        """测试从 Polars 创建 RecordBatch 流"""
        import polars as pl
        
        df = pl.DataFrame({
            'a': list(range(100)),
            'b': list(range(100, 200)),
        })
        
        batches = list(bridge.create_record_batch_stream(df, batch_size=30))
        
        assert len(batches) == 4
    
    def test_create_record_batch_stream_arrow(self, bridge):
        """测试从 Arrow Table 创建 RecordBatch 流"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': list(range(100)),
            'b': list(range(100, 200)),
        })
        
        batches = list(bridge.create_record_batch_stream(table, batch_size=30))
        
        assert len(batches) == 4


class TestArrowBridgeIPC:
    """Arrow Bridge IPC 序列化测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_serialize_to_ipc(self, bridge):
        """测试序列化为 IPC"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.serialize_to_ipc(table)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_deserialize_from_ipc(self, bridge):
        """测试从 IPC 反序列化"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        serialized = bridge.serialize_to_ipc(table)
        result = bridge.deserialize_from_ipc(serialized)
        
        assert result.num_rows == 3
        assert 'a' in result.column_names
    
    def test_roundtrip_ipc(self, bridge):
        """测试 IPC 往返序列化"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
            'c': ['x', 'y', 'z'],
        })
        
        serialized = bridge.serialize_to_ipc(table)
        result = bridge.deserialize_from_ipc(serialized)
        
        assert result.num_rows == 3
        assert result.column_names == table.column_names


class TestArrowBridgeTableOperations:
    """Arrow Bridge 表操作测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_merge_tables_empty(self, bridge):
        """测试合并空表列表"""
        result = bridge.merge_tables([])
        
        assert result.num_rows == 0
    
    def test_merge_tables_single(self, bridge):
        """测试合并单个表"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
        })
        
        result = bridge.merge_tables([table])
        
        assert result.num_rows == 3
    
    def test_merge_tables_multiple(self, bridge):
        """测试合并多个表"""
        import pyarrow as pa
        
        table1 = pa.Table.from_pydict({
            'a': [1, 2, 3],
        })
        table2 = pa.Table.from_pydict({
            'a': [4, 5, 6],
        })
        
        result = bridge.merge_tables([table1, table2])
        
        assert result.num_rows == 6
    
    def test_filter_table(self, bridge):
        """测试过滤表"""
        import pyarrow as pa
        import pyarrow.compute as pc
        
        table = pa.Table.from_pydict({
            'value': [10, 20, 30, 40, 50],
        })
        
        result = bridge.filter_table(table, pc.field("value") > 25)
        
        assert result.num_rows == 3
    
    def test_sort_table(self, bridge):
        """测试排序表"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'value': [30, 10, 50, 20, 40],
        })
        
        result = bridge.sort_table(table, [("value", "ascending")])
        
        values = result['value'].to_pylist()
        assert values == [10, 20, 30, 40, 50]


class TestArrowBridgeValidation:
    """Arrow Bridge 验证测试"""
    
    @pytest.fixture
    def bridge(self):
        """创建 Bridge 实例"""
        from data_svc.bridge.arrow_bridge import ArrowBridge
        
        return ArrowBridge()
    
    def test_validate_schema_success(self, bridge):
        """测试 Schema 验证成功"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'trade_date': pa.array([date(2024, 1, 1)], type=pa.date32()),
            'stock_code': ['000001.SZ'],
            'close': [10.0],
        })
        
        schema = pa.schema([
            ('trade_date', pa.date32()),
            ('stock_code', pa.string()),
            ('close', pa.float64()),
        ])
        
        result = bridge.validate_schema(table, schema)
        
        assert result is True
    
    def test_validate_schema_missing_column(self, bridge):
        """测试 Schema 验证缺少列"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'trade_date': pa.array([date(2024, 1, 1)], type=pa.date32()),
        })
        
        schema = pa.schema([
            ('trade_date', pa.date32()),
            ('stock_code', pa.string()),
        ])
        
        result = bridge.validate_schema(table, schema)
        
        assert result is False
    
    def test_get_table_stats(self, bridge):
        """测试获取表统计信息"""
        import pyarrow as pa
        
        table = pa.Table.from_pydict({
            'a': [1, 2, 3],
            'b': [4.0, 5.0, 6.0],
        })
        
        result = bridge.get_table_stats(table)
        
        assert result['num_rows'] == 3
        assert result['num_columns'] == 2
        assert 'a' in result['columns']
        assert 'b' in result['columns']
        assert result['size_bytes'] > 0
