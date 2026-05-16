"""
检查 quant/data 目录下的原始数据
"""
import json
from pathlib import Path

data_lake_dir = Path("quant/data/data_lake/2026-02-12")

print("="*60)
print("检查 quant/data/data_lake/2026-02-12/")
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
        print(f"   所有股票:")
        for s in stocks:
            print(f"     - {s.get('code')} {s.get('name')}: 连板{s.get('continue_num')}, 封单{s.get('order_amount', 0)/1e8:.2f}亿")
else:
    print(f"\n1. limit_up_filter.json: 不存在")

# 2. 检查 cleaned_data 中的 CSV
cleaned_dir = Path("quant/data/cleaned_data/2026-02-12")
matrix_path = cleaned_dir / "stock_feature_matrix.csv"

if matrix_path.exists():
    with open(matrix_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\n2. stock_feature_matrix.csv:")
    print(f"   总行数(含表头): {len(lines)}")
    print(f"   股票数量: {len(lines) - 1}")
else:
    print(f"\n2. stock_feature_matrix.csv: 不存在")
