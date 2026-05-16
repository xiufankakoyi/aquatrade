"""
重新导入龙头股数据，修复索引问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.service import DragonEyeService
from core.dragon_eye.manager import DragonEyeManager

service = DragonEyeService()
manager = DragonEyeManager()

print("="*60)
print("重新导入龙头股数据")
print("="*60)

# 1. 清空旧数据
print("\n1. 清空旧数据...")
try:
    lib = manager.arctic_mgr._get_or_create_library("factor")
    try:
        lib.delete("dragon_stock")
        print("   ✓ 已删除旧的 dragon_stock 数据")
    except Exception as e:
        print(f"   ! 删除旧数据时出错: {e}")
except Exception as e:
    print(f"   ! 无法访问 ArcticDB: {e}")

# 2. 重新导入所有日期的数据
print("\n2. 重新导入数据...")
data_lake_dir = service.data_lake_dir
date_dirs = sorted([d for d in data_lake_dir.iterdir() if d.is_dir()])

print(f"   发现 {len(date_dirs)} 个日期目录")

for date_dir in date_dirs:
    target_date = date_dir.name
    print(f"\n   处理 {target_date}...")
    
    try:
        service._persist_to_db(target_date, service.cleaned_data_dir / target_date)
        print(f"   ✓ {target_date} 导入完成")
    except Exception as e:
        print(f"   ✗ {target_date} 导入失败: {e}")

# 3. 验证数据
print("\n" + "="*60)
print("3. 验证数据")
print("="*60)

df = manager.get_historical_dragon("2026-01-01", "2026-12-31")
print(f"\n总记录数: {len(df)}")

if not df.is_empty():
    # 按日期统计
    if 'trade_date' in df.columns:
        date_counts = df.groupby('trade_date').agg(pl.count()).sort('trade_date')
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
