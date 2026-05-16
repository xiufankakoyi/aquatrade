"""
测试特定日期的数据查询
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()

# 测试前端可能使用的日期
test_dates = [
    "2026-02-20",  # 今天
    "2026-02-13",  # 截图中的日期
    "2026-02-12",  # 数据库最新数据
    "2026-02-11",  # 前一天
]

print("="*60)
print("测试龙头股数据查询")
print("="*60)

for date in test_dates:
    df = manager.get_historical_dragon(date, date)
    print(f"\n日期 {date}: {len(df)} 条")

print("\n" + "="*60)
print("测试市场情绪数据查询")
print("="*60)

for date in test_dates:
    df = manager.get_market_sentiment(date, date)
    print(f"\n日期 {date}: {len(df)} 条")

print("\n" + "="*60)
print("建议：")
print("如果前端选择的日期没有数据，会显示'暂无数据'")
print("需要将日期选择器改为数据库中存在的日期")
print("="*60)
