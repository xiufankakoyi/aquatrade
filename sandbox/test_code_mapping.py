"""
测试代码映射问题
"""
import os
import sys
import polars as pl
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.unified_data_manager import get_unified_manager

print("=" * 70)
print("测试代码映射")
print("=" * 70)

# 读取数据
manager = get_unified_manager()
df = manager.read('stock_daily', start_date='2025-01-01', end_date='2025-01-31')

print(f"\n数据形状: {df.shape}")
print(f"列名: {df.columns}")

# 检查 stock_code 列
if 'stock_code' in df.columns:
    codes = df['stock_code'].unique().sort().to_list()
    print(f"\n股票代码数量: {len(codes)}")
    print(f"前10个代码: {codes[:10]}")
    
    # 检查 000001
    if '000001' in codes or 1 in codes or '1' in codes:
        print(f"\n✓ 找到 000001")
        
        # 检查原始格式
        raw_codes = df['stock_code'].unique().to_list()
        for c in raw_codes:
            if str(c) in ['000001', '1', 1]:
                print(f"  原始格式: {c!r} (类型: {type(c).__name__})")
    else:
        print(f"\n✗ 未找到 000001")
        print(f"  代码示例: {codes[:20]}")

# 测试映射逻辑
stock_codes = [str(c).zfill(6) for c in codes]
print(f"\n转换后的代码示例: {stock_codes[:10]}")

# 原始映射逻辑（有问题）
code_replace_map_old = {str(c).strip().lstrip('0') or '0': i for i, c in enumerate(stock_codes)}
print(f"\n旧映射逻辑 (有问题):")
print(f"  映射示例: {list(code_replace_map_old.items())[:5]}")

# 正确的映射逻辑
code_replace_map_new = {}
for i, c in enumerate(stock_codes):
    # 支持多种格式
    code_replace_map_new[str(c).strip()] = i  # '000001'
    code_replace_map_new[str(c).strip().lstrip('0') or '0'] = i  # '1'
    code_replace_map_new[int(c) if str(c).strip().isdigit() else c] = i  # 1

print(f"\n新映射逻辑 (正确):")
print(f"  '000001' -> {code_replace_map_new.get('000001', 'NOT FOUND')}")
print(f"  '1' -> {code_replace_map_new.get('1', 'NOT FOUND')}")
print(f"  1 -> {code_replace_map_new.get(1, 'NOT FOUND')}")

print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)
