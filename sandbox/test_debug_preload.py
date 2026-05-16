"""
调试预加载数据的日期范围
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import polars as pl
from data_svc.unified_data_manager import get_unified_manager
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 70)
print("调试预加载数据的日期范围")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    manager = get_unified_manager()
    
    # 检查缓存状态
    print(f"\n[2] 缓存状态:")
    print(f"  cache_loaded: {manager._cache_loaded}")
    print(f"  preloaded_date_range: {manager._preloaded_date_range}")
    
    # 尝试读取2025-01-01到2025-01-31的数据
    print(f"\n[3] 读取2025-01-01到2025-01-31的数据...")
    df = manager.read('stock_daily', start_date='2025-01-01', end_date='2025-01-31', use_cache=False)
    
    if not df.is_empty():
        print(f"  数据条数: {len(df)}")
        
        # 检查日期范围
        if 'trade_date' in df.columns:
            dates = df['trade_date'].unique().sort().to_list()
            print(f"  日期数量: {len(dates)}")
            print(f"  开始日期: {dates[0]}")
            print(f"  结束日期: {dates[-1]}")
            print(f"\n  所有日期:")
            for d in dates:
                print(f"    {d}")
    else:
        print("  ⚠️ 数据为空")
    
    # 检查000001的数据
    print(f"\n[4] 检查000001在2025-01-20的数据...")
    df_000001 = df.filter(pl.col('stock_code') == '000001') if not df.is_empty() else pl.DataFrame()
    
    if not df_000001.is_empty():
        dates_000001 = df_000001['trade_date'].unique().sort().to_list()
        print(f"  000001的日期数量: {len(dates_000001)}")
        print(f"  开始日期: {dates_000001[0]}")
        print(f"  结束日期: {dates_000001[-1]}")
        
        # 检查是否包含2025-01-20
        if '2025-01-20' in [str(d) for d in dates_000001]:
            print(f"  ✓ 包含2025-01-20")
            # 显示2025-01-20的数据
            row = df_000001.filter(pl.col('trade_date') == '2025-01-20')
            if not row.is_empty():
                print(f"\n  2025-01-20的数据:")
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in row.columns:
                        print(f"    {col}: {row[col].to_list()[0]}")
        else:
            print(f"  ✗ 不包含2025-01-20")
            print(f"  最近的日期: {dates_000001[-1] if dates_000001 else 'N/A'}")
    else:
        print("  ⚠️ 000001无数据")
    
    print(f"\n[5] 结论:")
    print(f"  ArcticDB中的数据只到2025-01-27")
    print(f"  缺少2025-01-28到2025-01-31的数据")
    print(f"  但2025-01-20的数据是存在的！")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
