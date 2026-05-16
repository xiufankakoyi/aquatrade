"""
验证龙头股数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

import polars as pl
from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()

print("="*60)
print("验证龙头股数据")
print("="*60)

df = manager.get_historical_dragon("2026-01-01", "2026-12-31")
print(f"\n总记录数: {len(df)}")

if not df.is_empty():
    # 按日期统计
    if 'trade_date' in df.columns:
        date_counts = df.group_by('trade_date').agg(pl.count()).sort('trade_date')
        print(f"\n各日期记录数:")
        for row in date_counts.to_dicts():
            print(f"   {row['trade_date']}: {row['count']} 条")
    
    # 显示 2026-02-12 的详细数据
    df_0212 = manager.get_historical_dragon("2026-02-12", "2026-02-12")
    print(f"\n2026-02-12 详细数据 ({len(df_0212)} 条):")
    for row in df_0212.to_dicts()[:10]:
        print(f"   - {row.get('stock_code')} {row.get('stock_name')}: 连板{row.get('continue_num')}")
    if len(df_0212) > 10:
        print(f"   ... 还有 {len(df_0212) - 10} 条")
