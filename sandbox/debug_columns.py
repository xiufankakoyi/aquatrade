"""
检查 DataFrame 的所有列
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
from data_svc.unified_data_manager import UnifiedDataManager

# 创建数据管理器
data_manager = UnifiedDataManager()

# 读取数据
df = data_manager.read('stock_daily', start_date='2024-01-02', end_date='2024-01-10')

print(f"所有列 ({len(df.columns)}个):")
for i, col in enumerate(df.columns):
    print(f"  {i+1:2}. {col}")

# 检查是否有 is_suspended, is_limit_up, is_limit_down
suspicious_cols = [c for c in df.columns if 'is_' in c or 'limit' in c.lower()]
print(f"\n可疑列: {suspicious_cols}")

# 检查这些列的值
for col in suspicious_cols:
    print(f"\n{col}:")
    print(f"  类型: {df[col].dtype}")
    print(f"  唯一值: {df[col].unique().to_list()}")
