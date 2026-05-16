"""
检查ArcticDB数据的列名和结构
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

# 加载数据
manager = UnifiedDataManager()
df = manager.read(
    library='stock_daily',
    start_date='2024-01-01',
    end_date='2024-01-10',
    use_cache=False
)

print("数据形状:", df.shape)
print("\n数据列名:")
print(list(df.columns))

print("\n前5行数据:")
pdf = df.head().to_pandas()
print(pdf.to_string())

print("\n数据类型:")
print(df.dtypes)
