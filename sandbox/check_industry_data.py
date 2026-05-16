"""
检查可用的行业/板块数据
"""

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.unified_data_query import get_stock_basic, get_arctic_instance, get_libraries_cached, get_symbols_cached

print("="*80)
print("检查行业数据可用性")
print("="*80)

# 1. 检查 stock_basic 中的行业信息
print("\n【1. 检查 stock_basic 中的行业信息】")
print("-"*60)

df_basic = get_stock_basic()
if df_basic is not None and not df_basic.empty:
    print(f"stock_basic 数据行数: {len(df_basic)}")
    print(f"列名: {list(df_basic.columns)}")
    
    if 'industry' in df_basic.columns:
        print(f"\n行业字段存在！")
        print(f"行业数量: {df_basic['industry'].nunique()}")
        print(f"\n行业分布(前20):")
        print(df_basic['industry'].value_counts().head(20))
    else:
        print("\n⚠️ stock_basic 中没有 industry 字段")
else:
    print("⚠️ stock_basic 数据不可用")

# 2. 检查 ArcticDB 中是否有行业指数数据
print("\n\n【2. 检查 ArcticDB 中的库】")
print("-"*60)

arctic = get_arctic_instance()
libraries = get_libraries_cached()
print(f"可用库: {libraries}")

# 检查是否有指数相关的库
index_libs = [lib for lib in libraries if 'index' in lib.lower()]
print(f"\n指数相关库: {index_libs}")

for lib_name in index_libs[:3]:  # 检查前3个
    try:
        lib = arctic[lib_name]
        symbols = get_symbols_cached(lib_name)
        print(f"\n  {lib_name}: {len(symbols)} 个symbol")
        if len(symbols) > 0:
            print(f"    示例: {symbols[:10]}")
    except Exception as e:
        print(f"  {lib_name}: 读取失败 - {e}")

# 3. 检查 daily 库中的股票数据是否有行业字段
print("\n\n【3. 检查 daily 库数据结构】")
print("-"*60)

if 'daily' in libraries:
    try:
        lib = arctic['daily']
        symbols = get_symbols_cached('daily')
        print(f"daily 库股票数量: {len(symbols)}")
        
        if len(symbols) > 0:
            # 读取一个样本
            sample = lib.read(symbols[0])
            if hasattr(sample, 'data'):
                df_sample = sample.data
                print(f"\n样本股票 {symbols[0]} 的列名: {list(df_sample.columns)}")
                
                # 检查是否有行业相关字段
                industry_cols = [col for col in df_sample.columns if any(keyword in col.lower() for keyword in ['industry', 'sector', '行业', '板块'])]
                if industry_cols:
                    print(f"行业相关字段: {industry_cols}")
                else:
                    print("⚠️ 日线数据中没有行业相关字段")
    except Exception as e:
        print(f"读取 daily 库失败: {e}")

# 4. 检查是否有行业分类数据文件
print("\n\n【4. 检查本地行业分类文件】")
print("-"*60)

# 检查常见的行业分类文件路径
possible_paths = [
    Path(__file__).parent.parent / "data" / "industry_classification.csv",
    Path(__file__).parent.parent / "data" / "stock_industry.csv",
    Path(__file__).parent.parent / "config" / "industry.csv",
]

for path in possible_paths:
    if path.exists():
        print(f"✓ 找到行业文件: {path}")
        try:
            df = pd.read_csv(path)
            print(f"  行数: {len(df)}, 列名: {list(df.columns)}")
        except Exception as e:
            print(f"  读取失败: {e}")
    else:
        print(f"✗ 不存在: {path}")

print("\n\n" + "="*80)
print("结论")
print("="*80)
print("""
要进行板块收益分析，需要以下数据之一:

1. ✓ stock_basic 中的 industry 字段 - 可用于个股行业分类
2. ? 行业指数数据 - 需要检查是否有申万一级/二级行业指数
3. ? 概念板块数据 - 需要检查是否有概念板块指数

建议下一步:
- 如果 stock_basic 有 industry 字段，可以按行业分组统计个股收益
- 如果需要行业指数，需要从 Tushare 或其他数据源获取
""")
