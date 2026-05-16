"""
DragonEye 完整流程测试脚本
测试日期: 2026-02-10
流程: 爬虫 -> 清洗 -> 飞书推送
"""
import sys
import os
import subprocess
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("DragonEye 完整流程测试")
print("测试日期: 2026-02-10")
print("=" * 70)

# 动态查找quant目录
def find_quant_dir() -> Path:
    """动态查找quant目录位置"""
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        quant_candidate = parent / "quant"
        if quant_candidate.exists() and quant_candidate.is_dir():
            if (quant_candidate / "main_launcher.py").exists():
                return quant_candidate
    return project_root / "quant"

QUANT_DIR = find_quant_dir()
TARGET_DATE = "2026-02-10"

print(f"\n[配置信息]")
print(f"  quant目录: {QUANT_DIR}")
print(f"  目标日期: {TARGET_DATE}")

# 步骤1: 执行爬虫
print("\n" + "=" * 70)
print("[步骤1] 执行爬虫")
print("=" * 70)

main_launcher = QUANT_DIR / "main_launcher.py"
data_lake_dir = QUANT_DIR / "data" / "data_lake" / TARGET_DATE

print(f"  爬虫脚本: {main_launcher}")
print(f"  数据输出目录: {data_lake_dir}")

if data_lake_dir.exists():
    existing_files = list(data_lake_dir.glob("*.json"))
    print(f"  注意: 目录已存在，包含 {len(existing_files)} 个JSON文件")
    print(f"  将重新爬取数据...")

cmd = [sys.executable, str(main_launcher), TARGET_DATE]
print(f"\n  执行命令: {' '.join(cmd)}")
print(f"  工作目录: {QUANT_DIR}")
print(f"\n  开始爬取 (可能需要30-60秒)...")

start_time = time.time()
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    universal_newlines=True,
    encoding='utf-8',
    cwd=str(QUANT_DIR)
)

# 实时输出日志
output_lines = []
for line in process.stdout:
    line = line.strip()
    if line:
        output_lines.append(line)
        print(f"    {line}")

process.wait()
elapsed = time.time() - start_time

print(f"\n  爬虫完成，耗时: {elapsed:.1f}秒，返回码: {process.returncode}")

if process.returncode != 0:
    print("  ✗ 爬虫执行失败!")
    sys.exit(1)

# 验证爬虫数据
print("\n  验证爬虫数据...")
if data_lake_dir.exists():
    json_files = list(data_lake_dir.glob("*.json"))
    print(f"    ✓ 找到 {len(json_files)} 个JSON文件:")
    for f in sorted(json_files):
        size = f.stat().st_size / 1024  # KB
        print(f"      - {f.name} ({size:.1f} KB)")
else:
    print("    ✗ 数据目录不存在!")
    sys.exit(1)

# 步骤2: 执行数据清洗
print("\n" + "=" * 70)
print("[步骤2] 执行数据清洗")
print("=" * 70)

# 动态导入combined模块
import importlib.util
combined_path = QUANT_DIR / "combined.py"
spec = importlib.util.spec_from_file_location("combined", str(combined_path))
combined_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(combined_module)
StockDataCleaner = combined_module.StockDataCleaner

cleaned_data_dir = QUANT_DIR / "data" / "cleaned_data" / TARGET_DATE
cleaned_data_dir.mkdir(parents=True, exist_ok=True)

print(f"  输入目录: {data_lake_dir}")
print(f"  输出目录: {cleaned_data_dir}")
print(f"\n  开始清洗...")

try:
    cleaner = StockDataCleaner(str(data_lake_dir), str(cleaned_data_dir))
    cleaner.generate_market_dashboard()
    print("    ✓ market_dashboard.csv 生成完成")
    
    cleaner.generate_stock_feature_matrix()
    print("    ✓ stock_feature_matrix.csv 生成完成")
    
    cleaner.generate_ai_daily_brief()
    print("    ✓ ai_daily_brief.txt 生成完成")
    
    print("\n  ✓ 数据清洗完成!")
except Exception as e:
    print(f"\n  ✗ 清洗失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 验证清洗结果
brief_file = cleaned_data_dir / "ai_daily_brief.txt"
if brief_file.exists():
    content = brief_file.read_text(encoding='utf-8')
    print(f"\n  简报文件大小: {len(content)} 字符")
    print(f"\n  简报预览 (前500字符):")
    print("  " + "-" * 50)
    for line in content[:500].split('\n')[:10]:
        print(f"  {line}")
    print("  " + "-" * 50)
else:
    print("  ✗ 简报文件未生成!")
    sys.exit(1)

# 步骤3: 飞书推送
print("\n" + "=" * 70)
print("[步骤3] 飞书推送")
print("=" * 70)

# 从Config获取webhook
from config.config import Config
webhook_url = getattr(Config, 'FEISHU_WEBHOOK', "")

if not webhook_url:
    print("  ⚠ 未配置飞书Webhook (Config.FEISHU_WEBHOOK)")
    print("  跳过推送步骤")
    print("\n" + "=" * 70)
    print("测试完成 (未推送飞书)")
    print("=" * 70)
    sys.exit(0)

print(f"  Webhook: {webhook_url[:50]}...")
print(f"  开始推送...")

FeishuPush = combined_module.FeishuPush
try:
    pusher = FeishuPush(webhook_url)
    markdown = pusher.txt_to_markdown(content)
    success = pusher.push_markdown(markdown)
    
    if success:
        print("\n  ✓ 飞书推送成功!")
    else:
        print("\n  ✗ 飞书推送失败!")
        sys.exit(1)
except Exception as e:
    print(f"\n  ✗ 推送异常: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ 完整流程测试成功!")
print("=" * 70)
