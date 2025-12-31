import lancedb
import time
import pandas as pd
import os
from pathlib import Path

# 配置路径 (根据你的实际路径调整)
LANCE_DB_PATH = "./parquet_data/lance_db"
TABLE_NAME = "stock_daily"

def verify_sort():
    print("="*60)
    print(f"🔍 LanceDB 物理存储顺序验证工具")
    print(f"📂 目标路径: {LANCE_DB_PATH}")
    print("="*60)

    # 1. 连接数据库
    if not os.path.exists(LANCE_DB_PATH):
        print("❌ 错误: 数据库文件夹不存在！请先运行迁移脚本。")
        return

    db = lancedb.connect(LANCE_DB_PATH)
    if TABLE_NAME not in db.table_names():
        print(f"❌ 错误: 表 '{TABLE_NAME}' 不存在！")
        return

    table = db.open_table(TABLE_NAME)
    print(f"✅ 成功连接到表: {TABLE_NAME}")
    
    # 获取总行数
    row_count = table.count_rows()
    print(f"📊 总行数: {row_count:,}")

    # ---------------------------------------------------------
    # 测试 1: 物理首尾抽查 (Physical Head/Tail Check)
    # ---------------------------------------------------------
    print("\n[测试 1] 物理存储首尾抽查...")
    try:
        # 读取前 5 行
        head_df = table.search().limit(5).to_pandas()
        # 读取后 5 行 (LanceDB 没有直接的 tail，我们通过 offset 读取最后几行)
        tail_offset = max(0, row_count - 5)
        tail_df = table.to_pandas()[tail_offset:] 
        
        print(f"  👉 物理第一行日期: {head_df.iloc[0]['trade_date']} (代码: {head_df.iloc[0]['stock_code']})")
        print(f"  👉 物理最后一行日期: {tail_df.iloc[-1]['trade_date']} (代码: {tail_df.iloc[-1]['stock_code']})")
        
        # 简单判断
        if head_df.iloc[0]['trade_date'] > tail_df.iloc[-1]['trade_date']:
            print("  ❌ 警告: 头部日期晚于尾部日期，数据绝对是乱序的！")
        else:
            print("  ✅ 首尾时间顺序逻辑正常。")
            
    except Exception as e:
        print(f"  ⚠️ 无法读取首尾数据: {e}")

    # ---------------------------------------------------------
    # 测试 2: 严格单调性检查 (Strict Monotonicity Check)
    # ---------------------------------------------------------
    print("\n[测试 2] 严格排序检查 (只读取 trade_date 列)...")
    try:
        start_t = time.time()
        # 仅加载日期列，内存占用极小
        # 注意: 即使几百万行，只读一列 date 也是瞬间的
        df_dates = table.to_pandas(columns=['trade_date'])
        load_t = time.time() - start_t
        
        print(f"  📥 加载日期列耗时: {load_t:.4f}s")
        
        # 检查是否单调递增
        # check if trade_date is sorted
        is_sorted = df_dates['trade_date'].is_monotonic_increasing
        
        if is_sorted:
            print("  ✅ pass: 数据严格按时间顺序物理存储！")
        else:
            print("  ❌ FAIL: 数据存储是乱序的！")
            # 找出乱序的位置
            diffs = df_dates['trade_date'] < df_dates['trade_date'].shift(1)
            bad_indices = diffs[diffs].index.tolist()
            if bad_indices:
                first_bad = bad_indices[0]
                print(f"     乱序示例: 第 {first_bad} 行 ({df_dates.iloc[first_bad]['trade_date']}) 早于前一行")
                
    except Exception as e:
        print(f"  ⚠️ 检查失败: {e}")

    # ---------------------------------------------------------
    # 测试 3: 模拟你的“死亡查询” (Simulation)
    # ---------------------------------------------------------
    print("\n[测试 3] 模拟之前的 54秒 慢查询...")
    target_date = head_df.iloc[0]['trade_date'] # 使用表中存在的日期
    print(f"  🎯 查询目标日期: {target_date}")
    
    start_q = time.time()
    
    # 模拟 SQL: SELECT * FROM table WHERE trade_date = '...'
    # LanceDB pushdown filter
    result = table.search().where(f"trade_date = '{target_date}'").to_pandas()
    
    duration = time.time() - start_q
    
    print(f"  ⏱️ 查询耗时: {duration:.4f} 秒")
    print(f"  📄 结果行数: {len(result)}")
    
    if duration > 1.0:
        print("  ❌ 依然很慢！需要重新进行数据迁移 (migrate_to_lancedb.py)。")
    elif duration < 0.1:
        print("  🚀 极速！性能达标。")
    else:
        print("  ⚠️ 速度一般，但在可接受范围内。")

if __name__ == "__main__":
    verify_sort()