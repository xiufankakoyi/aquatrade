"""
调试股票过滤逻辑
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from data_svc.unified_data_query import get_stock_basic
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

pdf = df.to_pandas()
all_symbols = pdf['stock_code'].unique().tolist()
print(f"数据中的股票总数: {len(all_symbols)}")
print(f"前10个: {all_symbols[:10]}")

# 检查_is_index过滤
index_codes = [s for s in all_symbols if s.startswith('000') or s.startswith('399') or s.startswith('899')]
print(f"\n被识别为指数的数量: {len(index_codes)}")
print(f"指数示例: {index_codes[:10]}")

# 过滤后
stock_symbols = [s for s in all_symbols if not (s.startswith('000') or s.startswith('399') or s.startswith('899'))]
print(f"\n过滤后的股票数量: {len(stock_symbols)}")
print(f"股票示例: {stock_symbols[:10]}")

# 检查stock_basic
stock_basic = get_stock_basic()
if stock_basic is not None:
    print(f"\nstock_basic中的股票数量: {len(stock_basic)}")
    print(f"stock_basic代码示例: {stock_basic['ts_code'].tolist()[:10]}")
    
    # 检查交集
    basic_codes = stock_basic['ts_code'].tolist()
    intersection = [s for s in stock_symbols if s in basic_codes]
    print(f"\n交集数量: {len(intersection)}")
    print(f"交集示例: {intersection[:10]}")
else:
    print("\nstock_basic为空")
