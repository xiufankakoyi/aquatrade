"""
写入层 (Storage Layer)

负责极速写入 Tick 数据，压缩存储，管理时间切片。
使用 LanceDB 作为底层存储引擎。

架构位置:
┌─────────────────────────────────────────────────────────────────┐
│                        写入层 (LanceDB)                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ • 极速写入 Tick/分钟级数据 (Arrow 列式存储)                  │ │
│  │ • 向量检索支持 (未来扩展)                                    │ │
│  │ • 时间切片管理 (按 symbol + 时间范围分片)                    │ │
│  │ • 高压缩比存储 (Lance 格式)                                  │ │
│  │ • 支持实时流式写入                                          │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
"""

from .lancedb_manager import LanceDBManager, get_lancedb_manager
from .unified_reader import UnifiedDataReader, get_unified_reader, get_lancedb_reader

__all__ = [
    'LanceDBManager', 
    'get_lancedb_manager',
    'UnifiedDataReader',
    'get_unified_reader',
    'get_lancedb_reader',
]
