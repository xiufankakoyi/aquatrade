"""
验证 stock_basic 数据是否正确写入 ArcticDB
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config

try:
    from arcticdb import Arctic
    ARCTICDB_AVAILABLE = True
except ImportError:
    ARCTICDB_AVAILABLE = False
    print("[ERROR] ArcticDB 未安装")
    sys.exit(1)

# 连接 ArcticDB
arctic_path = getattr(Config, 'ARCTICDB_PATH', None) or "./data/arctic_db"
arctic = Arctic(f"lmdb://{arctic_path}")

# 检查库是否存在
if "stock_basic" not in arctic.list_libraries():
    print("[ERROR] stock_basic 库不存在")
    sys.exit(1)

lib = arctic["stock_basic"]

# 读取数据
try:
    data = lib.read("stock_list")
    df = data.data
    
    print("=" * 60)
    print("Stock Basic 数据验证报告")
    print("=" * 60)
    print(f"\n总记录数: {len(df)}")
    print(f"\n数据列 ({len(df.columns)} 个):")
    
    for i, col in enumerate(df.columns, 1):
        non_null = df[col].notna().sum()
        print(f"  {i:2d}. {col:20s} - 非空值: {non_null:5d} ({non_null/len(df)*100:.1f}%)")
    
    print("\n" + "=" * 60)
    print("前5条数据示例:")
    print("=" * 60)
    print(df.head().to_string())
    
    print("\n" + "=" * 60)
    print("板块分布统计:")
    print("=" * 60)
    if 'is_kc' in df.columns:
        kc_count = df['is_kc'].sum()
        print(f"  科创板: {kc_count} 只")
    if 'is_cy' in df.columns:
        cy_count = df['is_cy'].sum()
        print(f"  创业板: {cy_count} 只")
    if 'market' in df.columns:
        print(f"\n  市场分布:")
        print(df['market'].value_counts().to_string())
    if 'area' in df.columns:
        print(f"\n  地域分布 (前10):")
        print(df['area'].value_counts().head(10).to_string())
    if 'industry' in df.columns:
        print(f"\n  行业分布 (前10):")
        print(df['industry'].value_counts().head(10).to_string())
    
    print("\n" + "=" * 60)
    print("✅ 数据验证完成!")
    print("=" * 60)
    
except Exception as e:
    print(f"[ERROR] 读取数据失败: {e}")
    import traceback
    traceback.print_exc()
