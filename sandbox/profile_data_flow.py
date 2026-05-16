"""
top3_backtest.py 数据流程分析

分析：
1. 是否有零拷贝？
2. 主要耗时点在哪里？
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import numpy as np


def profile_data_flow():
    """分析数据流各环节"""
    print("=" * 60)
    print("top3_backtest.py 数据流程分析")
    print("=" * 60)
    
    from data_svc.storage.lancedb_reader import get_lancedb_reader
    
    start_date = "2026-01-01"
    end_date = "2026-03-13"
    
    # 步骤1: LanceDB 连接和读取
    print("\n[步骤1] LanceDB 读取")
    t0 = time.perf_counter()
    
    reader = get_lancedb_reader()
    fields = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
    
    # 这是关键 - read_as_dict 做了什么？
    # 1. reader.read() - 从 LanceDB 读取 Arrow Table
    # 2. df.partition_by() - 按股票分组（会复制数据）
    # 3. for each group: group[col].to_numpy() - Polars → NumPy（零拷贝？）
    # 4. 存入 dict
    
    daily_data = reader.read_as_dict(
        start_date=start_date,
        end_date=end_date,
        fields=fields,
    )
    step1_time = time.perf_counter() - t0
    print(f"  LanceDB 读取 + 字典构建: {step1_time*1000:.1f}ms")
    print(f"  返回类型: {type(daily_data)}")
    print(f"  股票数: {len(daily_data)}")
    
    if daily_data:
        sample_code = list(daily_data.keys())[0]
        sample_data = daily_data[sample_code]
        print(f"  样例 {sample_code}:")
        print(f"    类型: {type(sample_data)}")
        for k, v in sample_data.items():
            print(f"    {k}: type={type(v)}, len={len(v)}")
    
    # 步骤2: 日期字段重命名
    print("\n[步骤2] 字段重命名")
    t0 = time.perf_counter()
    for sc in daily_data:
        daily_data[sc]['dates'] = daily_data[sc].pop('trade_date')
    step2_time = time.perf_counter() - t0
    print(f"  字段重命名: {step2_time*1000:.1f}ms")
    
    # 步骤3: 数据类型检查
    print("\n[步骤3] 数据类型检查")
    sample = daily_data[list(daily_data.keys())[0]]
    print(f"  dates dtype: {sample['dates'].dtype}")
    print(f"  close dtype: {sample['close'].dtype}")
    print(f"  是否连续: {sample['close'].flags['C_CONTIGUOUS']}")
    
    print("\n" + "=" * 60)
    print("零拷贝分析")
    print("=" * 60)
    
    print("""
数据流分析:
    
1. LanceDB → Arrow Table (PyArrow)
   - LanceDB.to_arrow() 返回 PyArrow Table
   - 这是零拷贝（内存映射）
   
2. Arrow Table → Polars DataFrame
   - pl.from_arrow(arrow_table)
   - 这是零拷贝（引用同一块内存）
   
3. Polars DataFrame → partition_by 分组
   - partition_by() 会复制数据！
   - 这是有拷贝的
   
4. Polars Group → NumPy 数组
   - group[col].to_numpy()
   - 默认是零拷贝（使用 Arrow 底层）
   - 但如果需要连续内存，会有拷贝
   
5. NumPy 数组 → 存入 Dict
   - 这是引用传递，零拷贝
    
结论: 不是完全零拷贝，partition_by 环节有数据复制
""")
    
    print("\n" + "=" * 60)
    print("耗时占比分析")
    print("=" * 60)
    
    total = step1_time + step2_time
    print(f"步骤1 (LanceDB读取): {step1_time*1000:.1f}ms ({step1_time/total*100:.1f}%)")
    print(f"步骤2 (字段重命名): {step2_time*1000:.1f}ms ({step2_time/total*100:.1f}%)")
    print(f"总计: {total*1000:.1f}ms")


if __name__ == "__main__":
    profile_data_flow()
