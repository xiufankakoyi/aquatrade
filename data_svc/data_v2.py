"""
数据回补引擎 (Data Backfill Engine)
====================================

【说明】
此模块已从 LanceDB 迁移到 ArcticDB 两层架构。
如需使用，请配置 DB_BACKEND=arcticdb 并参考 arcticdb_updater.py

【迁移原因】
- LanceDB 已被移除，替换为 ArcticDB + Polars 两层架构
- 新架构提供更好的写入性能、压缩率和查询效率

【替代方案】
使用 data_svc/storage/arcticdb_updater.py 进行数据同步
"""
import warnings

warnings.warn(
    "data_v2.py 已弃用，请使用 data_svc/storage/arcticdb_updater.py 进行数据同步",
    DeprecationWarning,
    stacklevel=2
)

# 保留导入以便兼容，但功能已迁移
from data_svc.storage.arcticdb_updater import ArcticDBUpdater

__all__ = ['ArcticDBUpdater']
