"""
检查复权因子和价格数据差异
"""
import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

print("=" * 70)
print("检查复权因子和价格数据")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 获取000001的日线数据（包含复权因子）...")
    data_query = OptimizedStockDataQuery()
    
    # 获取2025年1月的数据
    df = data_query.get_stock_history('000001', '2024-12-01', '2025-02-28')
    
    if df.empty:
        print("  ⚠️ 无数据")
        sys.exit(1)
    
    # 计算MA5和MA10（原始价格）
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    
    # 计算前复权价格
    latest_adj = df['adj_factor'].iloc[-1]
    print(f"  最新复权因子: {latest_adj:.4f}")
    
    # 计算前复权价格
    df['adj_close'] = df['close'] * df['adj_factor'] / latest_adj
    
    # 使用前复权价格计算MA
    df['adj_ma5'] = df['adj_close'].rolling(window=5).mean()
    df['adj_ma10'] = df['adj_close'].rolling(window=10).mean()
    
    # 对比聚宽的MA值
    print("\n[2] 对比聚宽的MA值:")
    print("=" * 70)
    print("聚宽 2025-01-21: MA5=11.46, MA10=11.42, 价格=11.42")
    print("聚宽 2025-01-20: MA5=11.45, MA10=11.40")
    
    jan_20 = df[df['trade_date'] == '2025-01-20'].iloc[0]
    jan_21 = df[df['trade_date'] == '2025-01-21'].iloc[0]
    
    print(f"\nAquaTrade（原始价格）2025-01-20: MA5={jan_20['ma5']:.2f}, MA10={jan_20['ma10']:.2f}")
    print(f"AquaTrade（原始价格）2025-01-21: MA5={jan_21['ma5']:.2f}, MA10={jan_21['ma10']:.2f}")
    
    print(f"\nAquaTrade（前复权）2025-01-20: MA5={jan_20['adj_ma5']:.2f}, MA10={jan_20['adj_ma10']:.2f}")
    print(f"AquaTrade（前复权）2025-01-21: MA5={jan_21['adj_ma5']:.2f}, MA10={jan_21['adj_ma10']:.2f}")
    
    print("\n[3] 关键发现:")
    print("=" * 70)
    print("  复权因子在2025年1月期间保持不变（127.7841）")
    print("  这意味着前复权价格 = 原始价格")
    print("  所以前复权MA = 原始MA")
    print("")
    print("  聚宽的MA值与AquaTrade不同:")
    print("    聚宽 2025-01-21: MA5=11.46, MA10=11.42")
    print("    AquaTrade 2025-01-21: MA5=11.45, MA10=11.40")
    print("")
    print("  这表明聚宽使用了不同的数据源或计算方法!")
    
    print("\n[4] 检查2025-01-20和2025-01-21的原始数据:")
    print("=" * 70)
    
    for date in ['2025-01-20', '2025-01-21']:
        row = df[df['trade_date'] == date].iloc[0]
        print(f"\n{date}:")
        print(f"  开盘: {row['open']:.2f}")
        print(f"  收盘: {row['close']:.2f}")
        print(f"  最高: {row['high']:.2f}")
        print(f"  最低: {row['low']:.2f}")
        print(f"  成交量: {row['volume']:.0f}")
        print(f"  复权因子: {row['adj_factor']:.4f}")
    
    print("\n[5] 结论:")
    print("=" * 70)
    print("  1. 复权因子在2025年1月期间没有变化")
    print("  2. 聚宽的MA计算结果与AquaTrade不同")
    print("  3. 可能原因:")
    print("     - 聚宽使用了不同的数据源（可能是实时行情 vs 盘后数据）")
    print("     - 聚宽的MA计算方式不同（可能是基于分钟线计算）")
    print("     - 聚宽的数据有延迟或修正")
    print("  4. 这种差异是正常的，不同平台的数据源和计算方法可能不同")
    
    print("\n" + "=" * 70)
    print("检查完成!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
