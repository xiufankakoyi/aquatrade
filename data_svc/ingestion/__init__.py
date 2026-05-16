"""
数据摄入层 (Data Ingestion Layer)
================================

统一的数据写入管道，支持：
- 双源写入收敛（Tushare + Crawler）
- Redis 水位表管理
- 原子操作保证
- 自愈机制

核心组件：
- WatermarkManager: 水位表管理器
- ingestion_pipeline: 统一写入漏斗
- CrawlerEtiquette: 爬虫行为规范包装器
"""

from data_svc.ingestion.watermark_manager import (
    WatermarkManager,
    get_watermark_manager,
)
from data_svc.ingestion.ingestion_pipeline import (
    ingestion_pipeline,
    DataIngestionWriter,
    IngestionResult,
)
from data_svc.ingestion.crawler_etiquette import (
    CrawlerEtiquette,
    crawler_retry,
    random_delay,
    rotate_user_agent,
)
from data_svc.ingestion.gap_checker import (
    check_data_gaps,
    check_and_repair_gaps,
    GapCheckResult,
)
from data_svc.ingestion.dragon_eye_adapter import (
    DragonEyeAdapter,
    DragonEyeTransformer,
)

__all__ = [
    "WatermarkManager",
    "get_watermark_manager",
    "ingestion_pipeline",
    "DataIngestionWriter",
    "IngestionResult",
    "CrawlerEtiquette",
    "crawler_retry",
    "random_delay",
    "rotate_user_agent",
    "check_data_gaps",
    "check_and_repair_gaps",
    "GapCheckResult",
    "DragonEyeAdapter",
    "DragonEyeTransformer",
]
