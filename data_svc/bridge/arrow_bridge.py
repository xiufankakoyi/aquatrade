"""
交互层: Apache Arrow 数据桥梁
负责内存中的数据格式标准化和零拷贝传输

架构位置:
┌─────────────────────────────────────────────────────────────────┐
│                      交互层 (Apache Arrow)                       │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ • 内存数据格式标准 (零拷贝共享)                               │ │
│  │ • Arrow Flight 协议 (高速数据传输)                           │ │
│  │ • Arrow IPC 格式 (进程间通信)                                │ │
│  │ • 统一数据桥梁 (连接写入层和分析层)                           │ │
│  │ • 支持 Arrow RecordBatch 流式处理                            │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

架构连接:
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  ArcticDB   │ --> │ ArrowBridge │ --> │   Polars    │
    │  (写入层)    │     │ (交互层)     │     │  (分析层)    │
    └─────────────┘     └─────────────┘     └─────────────┘

技术特点:
- 零拷贝: 避免内存复制，提升性能
- 标准化: 成为数据科学的事实标准
- 生态丰富: 支持 Flight、IPC 等多种传输协议
- 语言无关: 便于未来扩展其他语言组件
"""

from typing import Optional, List, Dict, Union, Any, Iterator, Callable
from datetime import datetime, date
import pandas as pd
import numpy as np
from loguru import logger

# Arrow 导入
try:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.ipc as ipc
    from pyarrow import RecordBatch, Table, Schema
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False
    logger.warning("PyArrow not installed. Run: pip install pyarrow")

# Polars 导入 (用于与 Arrow 无缝集成)
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False


class ArrowBridge:
    """
    Arrow 数据桥梁
    
    核心功能:
    1. 数据格式转换: Pandas/Polars/ArcticDB -> Arrow
    2. 零拷贝共享: 避免内存复制，提升性能
    3. 流式处理: 支持 Arrow RecordBatch 流
    4. 数据校验: Arrow Schema 验证
    
    架构位置:
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  ArcticDB   │ --> │ ArrowBridge │ --> │   Polars    │
    │  (写入层)    │     │ (交互层)     │     │  (分析层)    │
    └─────────────┘     └─────────────┘     └─────────────┘
    
    使用示例:
        >>> bridge = ArrowBridge()
        >>>
        >>> # 从 LanceDB 读取并转换为 Arrow
        >>> df = lancedb_manager.read_data("daily", "000001.SZ")
        >>> arrow_table = bridge.from_pandas(df)
        >>>
        >>> # 传递给 Polars 进行分析
        >>> result = polars_analytics.from_arrow(arrow_table)
    """
    
    # 标准 Arrow Schema 定义 - 股票日线数据
    STOCK_DAILY_SCHEMA = pa.schema([
        ("trade_date", pa.date32()),
        ("stock_code", pa.string()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.int64()),
        ("amount", pa.float64()),
        ("adj_factor", pa.float64()),
        ("prev_close", pa.float64()),
    ])
    
    # Tick 数据 Schema
    TICK_SCHEMA = pa.schema([
        ("timestamp", pa.timestamp('ms')),
        ("stock_code", pa.string()),
        ("price", pa.float64()),
        ("volume", pa.int64()),
        ("amount", pa.float64()),
        ("bid1", pa.float64()),
        ("ask1", pa.float64()),
        ("bid1_volume", pa.int64()),
        ("ask1_volume", pa.int64()),
    ])
    
    # 因子数据 Schema
    FACTOR_SCHEMA = pa.schema([
        ("trade_date", pa.date32()),
        ("stock_code", pa.string()),
        ("rsi_14", pa.float64()),
        ("macd_dif", pa.float64()),
        ("macd_dea", pa.float64()),
        ("macd_hist", pa.float64()),
        ("kdj_k", pa.float64()),
        ("kdj_d", pa.float64()),
        ("kdj_j", pa.float64()),
    ])
    
    def __init__(self):
        """初始化 Arrow Bridge"""
        if not ARROW_AVAILABLE:
            raise ImportError(
                "PyArrow is required. Install with: pip install pyarrow"
            )
        
        self._buffer: List[RecordBatch] = []
        self._schema_cache: Dict[str, Schema] = {}
        
        logger.info("[ArrowBridge] 初始化完成")
    
    def from_pandas(
        self,
        df: pd.DataFrame,
        schema: Optional[Schema] = None,
        preserve_index: bool = True
    ) -> Table:
        """
        将 Pandas DataFrame 转换为 Arrow Table
        
        Args:
            df: Pandas DataFrame
            schema: 可选的 Arrow Schema，用于数据验证
            preserve_index: 是否保留索引
            
        Returns:
            Arrow Table
            
        Example:
            >>> df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
            >>> table = bridge.from_pandas(df)
        """
        if df.empty:
            # 返回空表
            if schema:
                return pa.Table.from_pydict({name: [] for name in schema.names}, schema=schema)
            else:
                return pa.Table.from_pandas(df)
        
        try:
            table = pa.Table.from_pandas(df, preserve_index=preserve_index)
            
            # 如果提供了 schema，进行验证和转换
            if schema:
                table = self._apply_schema(table, schema)
            
            return table
            
        except Exception as e:
            logger.error(f"[ArrowBridge] Pandas 转换失败: {e}")
            raise
    
    def to_pandas(self, table: Table) -> pd.DataFrame:
        """
        将 Arrow Table 转换为 Pandas DataFrame
        
        Args:
            table: Arrow Table
            
        Returns:
            Pandas DataFrame
        """
        try:
            return table.to_pandas()
        except Exception as e:
            logger.error(f"[ArrowBridge] 转换为 Pandas 失败: {e}")
            raise
    
    def from_polars(self, df: "pl.DataFrame", schema: Optional[Schema] = None) -> Table:
        """
        将 Polars DataFrame 转换为 Arrow Table (零拷贝)
        
        Args:
            df: Polars DataFrame
            schema: 可选的 Arrow Schema
            
        Returns:
            Arrow Table
            
        Note:
            Polars 使用 Arrow 作为内存格式，因此这是零拷贝转换
        """
        if not POLARS_AVAILABLE:
            raise ImportError("Polars is required. Install with: pip install polars")
        
        try:
            # Polars 内部就是 Arrow，直接转换
            arrow_table = df.to_arrow()
            
            if schema:
                arrow_table = self._apply_schema(arrow_table, schema)
            
            return arrow_table
            
        except Exception as e:
            logger.error(f"[ArrowBridge] Polars 转换失败: {e}")
            raise
    
    def to_polars(self, table: Table) -> "pl.DataFrame":
        """
        将 Arrow Table 转换为 Polars DataFrame (零拷贝)
        
        Args:
            table: Arrow Table
            
        Returns:
            Polars DataFrame
        """
        if not POLARS_AVAILABLE:
            raise ImportError("Polars is required. Install with: pip install polars")
        
        try:
            # 零拷贝转换
            return pl.from_arrow(table)
        except Exception as e:
            logger.error(f"[ArrowBridge] 转换为 Polars 失败: {e}")
            raise
    
    def _apply_schema(self, table: Table, schema: Schema) -> Table:
        """
        应用 Schema，进行列类型转换和验证
        
        Args:
            table: 输入表
            schema: 目标 schema
            
        Returns:
            转换后的表
        """
        # 检查列是否存在
        missing_cols = set(schema.names) - set(table.column_names)
        if missing_cols:
            # 添加缺失列，填充 null
            for col in missing_cols:
                table = table.append_column(col, pa.array([None] * len(table), type=schema.field(col).type))
        
        # 按 schema 顺序选择列并转换类型
        columns = []
        for field in schema:
            col_name = field.name
            if col_name in table.column_names:
                col = table[col_name]
                # 类型转换
                if col.type != field.type:
                    try:
                        col = col.cast(field.type)
                    except Exception as e:
                        logger.warning(f"[ArrowBridge] 列 {col_name} 类型转换失败: {e}")
                columns.append(col)
            else:
                # 填充 null
                columns.append(pa.array([None] * len(table), type=field.type))
        
        return pa.Table.from_arrays(columns, names=schema.names)
    
    def create_record_batch_stream(
        self,
        data_source: Union[Table, "pl.DataFrame", pd.DataFrame],
        batch_size: int = 10000
    ) -> Iterator[RecordBatch]:
        """
        创建 RecordBatch 流，用于大数据集的分块处理
        
        Args:
            data_source: 数据源 (Arrow Table, Polars DataFrame, 或 Pandas DataFrame)
            batch_size: 每个 batch 的行数
            
        Yields:
            RecordBatch
            
        应用场景:
        - 回测时流式加载历史数据
        - 避免一次性加载全部数据到内存
        - 大数据集的批处理
        
        Example:
            >>> for batch in bridge.create_record_batch_stream(large_table, batch_size=5000):
            ...     # 处理每个 batch
            ...     process_batch(batch)
        """
        # 统一转换为 Arrow Table
        if isinstance(data_source, pd.DataFrame):
            table = self.from_pandas(data_source)
        elif POLARS_AVAILABLE and isinstance(data_source, pl.DataFrame):
            table = self.from_polars(data_source)
        elif isinstance(data_source, Table):
            table = data_source
        else:
            raise ValueError(f"不支持的数据源类型: {type(data_source)}")
        
        # 分块
        total_rows = len(table)
        for i in range(0, total_rows, batch_size):
            batch = table.slice(i, min(batch_size, total_rows - i))
            yield batch.to_batches()[0]
    
    def serialize_to_ipc(self, table: Table) -> bytes:
        """
        将 Arrow Table 序列化为 IPC 格式 (用于网络传输或进程间通信)
        
        Args:
            table: Arrow Table
            
        Returns:
            IPC 格式的字节数据
        """
        sink = pa.BufferOutputStream()
        with ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)
        return sink.getvalue().to_pybytes()
    
    def deserialize_from_ipc(self, data: bytes) -> Table:
        """
        从 IPC 格式反序列化为 Arrow Table
        
        Args:
            data: IPC 格式的字节数据
            
        Returns:
            Arrow Table
        """
        buf = pa.py_buffer(data)
        with ipc.open_file(buf) as reader:
            return reader.read_all()
    
    def merge_tables(self, tables: List[Table]) -> Table:
        """
        合并多个 Arrow Table
        
        Args:
            tables: Table 列表
            
        Returns:
            合并后的 Table
        """
        if not tables:
            return pa.Table.from_pydict({})
        
        if len(tables) == 1:
            return tables[0]
        
        # 使用 pyarrow.concat_tables
        return pa.concat_tables(tables)
    
    def filter_table(
        self,
        table: Table,
        filter_expr: pc.Expression
    ) -> Table:
        """
        使用 Arrow 表达式过滤表
        
        Args:
            table: 输入表
            filter_expr: Arrow 计算表达式
            
        Returns:
            过滤后的表
            
        Example:
            >>> filtered = bridge.filter_table(
            ...     table,
            ...     pc.field("close") > 100
            ... )
        """
        mask = filter_expr
        return table.filter(mask)
    
    def sort_table(
        self,
        table: Table,
        sort_keys: List[tuple]
    ) -> Table:
        """
        对表进行排序
        
        Args:
            table: 输入表
            sort_keys: 排序键列表，每个元素为 (列名, 升序/降序)
                      例如: [("trade_date", "ascending"), ("stock_code", "ascending")]
            
        Returns:
            排序后的表
        """
        columns = []
        for col_name, order in sort_keys:
            if order == "ascending":
                columns.append((col_name, "ascending"))
            else:
                columns.append((col_name, "descending"))
        
        return table.sort_by(columns)
    
    def get_schema(self, data_type: str = "daily") -> Schema:
        """
        获取标准 Schema
        
        Args:
            data_type: 数据类型 ("daily", "tick", "factor")
            
        Returns:
            Arrow Schema
        """
        schemas = {
            "daily": self.STOCK_DAILY_SCHEMA,
            "tick": self.TICK_SCHEMA,
            "factor": self.FACTOR_SCHEMA,
        }
        return schemas.get(data_type, self.STOCK_DAILY_SCHEMA)
    
    def validate_schema(self, table: Table, schema: Schema) -> bool:
        """
        验证表是否符合 Schema
        
        Args:
            table: 输入表
            schema: 期望的 schema
            
        Returns:
            是否通过验证
        """
        table_schema = table.schema
        
        # 检查列名
        if set(table_schema.names) != set(schema.names):
            logger.warning(f"[ArrowBridge] 列名不匹配: {table_schema.names} vs {schema.names}")
            return False
        
        # 检查类型
        for field in schema:
            table_field = table_schema.field(field.name)
            if table_field.type != field.type:
                logger.warning(f"[ArrowBridge] 列 {field.name} 类型不匹配: {table_field.type} vs {field.type}")
                return False
        
        return True
    
    def get_table_stats(self, table: Table) -> Dict[str, Any]:
        """
        获取表的统计信息
        
        Args:
            table: Arrow Table
            
        Returns:
            统计信息字典
        """
        return {
            "num_rows": len(table),
            "num_columns": len(table.column_names),
            "columns": table.column_names,
            "schema": str(table.schema),
            "size_bytes": table.nbytes,
        }


# 全局实例管理
_arrow_bridge_instance: Optional[ArrowBridge] = None


def get_arrow_bridge() -> ArrowBridge:
    """
    获取 ArrowBridge 单例
    
    Returns:
        ArrowBridge 实例
    """
    global _arrow_bridge_instance
    
    if _arrow_bridge_instance is None:
        _arrow_bridge_instance = ArrowBridge()
    
    return _arrow_bridge_instance


def reset_arrow_bridge() -> None:
    """重置单例（用于测试）"""
    global _arrow_bridge_instance
    _arrow_bridge_instance = None
