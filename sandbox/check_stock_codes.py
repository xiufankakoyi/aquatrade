"""
检查股票代码格式
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

pdf = df.to_pandas()
print("股票代码示例:")
print(pdf['stock_code'].unique()[:20].tolist())
print(f"\n总股票数: {pdf['stock_code'].nunique()}")

# 检查代码格式
sample_codes = pdf['stock_code'].unique()[:50]
sh_codes = [c for c in sample_codes if c.endswith('.SH')]
sz_codes = [c for c in sample_codes if c.endswith('.SZ')]
bj_codes = [c for c in sample_codes if c.endswith('.BJ')]

print(f"\n上海股票(.SH): {len(sh_codes)} 个示例: {sh_codes[:5]}")
print(f"深圳股票(.SZ): {len(sz_codes)} 个示例: {sz_codes[:5]}")
print(f"北京股票(.BJ): {len(bj_codes)} 个示例: {bj_codes[:5]}")
