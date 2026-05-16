"""
检查龙头股数据存储情况
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()

print("="*60)
print("检查龙头股数据")
print("="*60)

# 测试不同日期范围
test_ranges = [
    ("2026-02-12", "2026-02-12"),
    ("2026-02-11", "2026-02-12"),
    ("2026-02-01", "2026-02-20"),
    ("2026-01-01", "2026-02-20"),
]

for start, end in test_ranges:
    df = manager.get_historical_dragon(start, end)
    print(f"\n{start} ~ {end}: {len(df)} 条")
    if not df.is_empty():
        print(f"  列: {df.columns}")
        if 'trade_date' in df.columns:
            print(f"  日期: {df['trade_date'].unique().to_list()}")

# 检查市场情绪数据
print("\n" + "="*60)
print("检查市场情绪数据")
print("="*60)

for start, end in test_ranges:
    df = manager.get_market_sentiment(start, end)
    print(f"\n{start} ~ {end}: {len(df)} 条")
    if not df.is_empty() and 'trade_date' in df.columns:
        print(f"  日期: {df['trade_date'].unique().to_list()}")
