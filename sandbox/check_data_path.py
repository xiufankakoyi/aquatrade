"""
检查数据加载路径
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager, get_unified_manager

# 获取管理器
manager = get_unified_manager()

print(f"缓存状态: cache_loaded={manager._cache_loaded}")
print(f"缓存范围: {manager._preloaded_date_range}")

# 尝试读取数据
df = manager.read('stock_daily', start_date='2025-06-01', end_date='2025-06-30')
print(f"\n读取 stock_daily (2025-06-01 ~ 2025-06-30): {len(df)} 行")

if not df.is_empty():
    print(f"列名: {df.columns}")
    print(f"\n日期范围:")
    dates = df['trade_date'].unique().sort().to_list()
    print(f"  {dates[0]} ~ {dates[-1]}")
    print(f"  共 {len(dates)} 个交易日")
    
    print(f"\n股票数量: {df['stock_code'].n_unique()}")
