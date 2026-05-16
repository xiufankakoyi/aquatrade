"""
检查原始数据文件中的股票数量
"""
import json
from pathlib import Path

data_lake_dir = Path("data/dragon_eye/data_lake/2026-02-12")

print("="*60)
print("检查 2026-02-12 的数据文件")
print("="*60)

# 1. 检查 limit_up_filter.json
limit_up_path = data_lake_dir / "limit_up_filter.json"
if limit_up_path.exists():
    with open(limit_up_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stocks = data.get('data', {}).get('stocks', [])
    print(f"\n1. limit_up_filter.json:")
    print(f"   股票数量: {len(stocks)}")
    if stocks:
        print(f"   前5只股票:")
        for s in stocks[:5]:
            print(f"     - {s.get('code')} {s.get('name')}: 连板{s.get('continue_num')}")
else:
    print(f"\n1. limit_up_filter.json: 不存在")

# 2. 检查 cleaned_data 中的 CSV
cleaned_dir = Path("data/dragon_eye/cleaned_data/2026-02-12")
matrix_path = cleaned_dir / "stock_feature_matrix.csv"

if matrix_path.exists():
    with open(matrix_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\n2. stock_feature_matrix.csv:")
    print(f"   总行数(含表头): {len(lines)}")
    print(f"   股票数量: {len(lines) - 1}")
    if len(lines) > 1:
        print(f"   前5行:")
        for line in lines[:6]:
            print(f"     {line.strip()}")
else:
    print(f"\n2. stock_feature_matrix.csv: 不存在")

# 3. 检查数据库中的数据
print(f"\n3. 数据库中的数据:")
import sys
sys.path.insert(0, "server")
from core.dragon_eye.manager import DragonEyeManager

manager = DragonEyeManager()
df = manager.get_historical_dragon("2026-02-12", "2026-02-12")
print(f"   股票数量: {len(df)}")
if not df.is_empty():
    print(f"   列名: {df.columns}")
    print(f"   数据:")
    for row in df.to_dicts():
        print(f"     - {row.get('stock_code')} {row.get('stock_name')}: 连板{row.get('continue_num')}")
