"""
DragonEye 路径配置测试脚本
验证路径计算是否正确，不实际执行爬虫
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("DragonEye 路径配置测试")
print("=" * 60)

# 测试1: 验证quant目录查找函数
print("\n[测试1] 查找quant目录...")
from core.dragon_eye.service import _find_quant_dir, QUANT_DIR

print(f"  找到的quant目录: {QUANT_DIR}")
print(f"  目录是否存在: {QUANT_DIR.exists()}")

if QUANT_DIR.exists():
    print(f"  ✓ quant目录存在")
else:
    print(f"  ✗ quant目录不存在!")
    sys.exit(1)

# 测试2: 验证关键文件是否存在
print("\n[测试2] 验证关键文件...")
required_files = [
    ("main_launcher.py", "爬虫入口"),
    ("combined.py", "数据清洗"),
    ("data/data_lake", "数据湖目录"),
    ("data/cleaned_data", "清洗后数据目录"),
]

all_ok = True
for filename, desc in required_files:
    filepath = QUANT_DIR / filename
    exists = filepath.exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {desc}: {filepath}")
    if not exists:
        all_ok = False

if not all_ok:
    print("\n✗ 部分关键文件缺失!")
    sys.exit(1)

# 测试3: 验证DragonEyeService初始化
print("\n[测试3] 初始化DragonEyeService...")
try:
    from core.dragon_eye.service import DragonEyeService
    service = DragonEyeService()
    print(f"  ✓ DragonEyeService初始化成功")
    print(f"    - quant_dir: {service.quant_dir}")
    print(f"    - spider_path: {service.spider_path}")
    print(f"    - cleaner_path: {service.cleaner_path}")
    print(f"    - data_lake_dir: {service.data_lake_dir}")
    print(f"    - cleaned_data_dir: {service.cleaned_data_dir}")
except Exception as e:
    print(f"  ✗ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: 验证路径正确性
print("\n[测试4] 验证路径正确性...")
checks = [
    (service.spider_path.exists(), f"spider_path存在: {service.spider_path}"),
    (service.cleaner_path.exists(), f"cleaner_path存在: {service.cleaner_path}"),
    (service.data_lake_dir.exists(), f"data_lake_dir存在: {service.data_lake_dir}"),
    (service.cleaned_data_dir.exists(), f"cleaned_data_dir存在: {service.cleaned_data_dir}"),
]

for ok, msg in checks:
    status = "✓" if ok else "✗"
    print(f"  {status} {msg}")

# 测试5: 列出data_lake中的已有数据
print("\n[测试5] 检查已有数据...")
if service.data_lake_dir.exists():
    dates = [d.name for d in service.data_lake_dir.iterdir() if d.is_dir()]
    dates.sort(reverse=True)
    print(f"  找到 {len(dates)} 个日期目录:")
    for date in dates[:5]:
        date_path = service.data_lake_dir / date
        files = list(date_path.glob("*.json"))
        print(f"    - {date}: {len(files)} 个JSON文件")
    if len(dates) > 5:
        print(f"    ... 还有 {len(dates)-5} 个目录")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
