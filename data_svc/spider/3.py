import pandas as pd
import os
import shutil
from datetime import datetime

# ================= 配置区 =================
# 指向你现在的数据库文件路径
PARQUET_FILE = 'D:/aquatrade/parquet_data/guba_posts.parquet'  
# 指向你的新 CSV 文件路径
CSV_FILE = 'D:/aquatrade/spider/data/000592_posts_12months.csv'
# ==========================================

def merge_csv_to_parquet():
    print(f"1. 正在读取 CSV 文件: {CSV_FILE}...")
    try:
        df_new = pd.read_csv(CSV_FILE)
        print(f"   -> 成功读取 {len(df_new)} 条新数据")
    except Exception as e:
        print(f"❌ 读取 CSV 失败: {e}")
        return

    # 检查 Parquet 是否存在
    if os.path.exists(PARQUET_FILE):
        print(f"2. 正在读取现有 Parquet 数据库: {PARQUET_FILE}...")
        try:
            df_old = pd.read_parquet(PARQUET_FILE)
            print(f"   -> 现有数据库包含 {len(df_old)} 条数据")
            
            # --- 关键步骤：备份旧文件 (防止误操作后悔) ---
            backup_name = PARQUET_FILE + f".bak_{datetime.now().strftime('%H%M%S')}"
            shutil.copy(PARQUET_FILE, backup_name)
            print(f"   -> 已自动备份原数据库为: {backup_name}")
            
        except Exception as e:
            print(f"⚠️ 读取 Parquet 出错 (可能文件损坏或为空): {e}")
            df_old = pd.DataFrame() # 如果读不出来，就当它是空的
    else:
        print("2. 未找到现有数据库，将创建新文件。")
        df_old = pd.DataFrame()

    # ==========================================
    # 核心逻辑：合并与清洗
    # ==========================================
    
    # 1. 如果旧数据库有数据，以旧数据库的列为准
    if not df_old.empty:
        # 找出 CSV 里有但 Parquet 里没有的列，丢弃（防止前端报错）
        common_cols = [c for c in df_new.columns if c in df_old.columns]
        df_new = df_new[common_cols]
        
        # 找出 Parquet 里有但 CSV 里没有的列，补空值
        for col in df_old.columns:
            if col not in df_new.columns:
                df_new[col] = None 
                
        # 确保顺序一致
        df_new = df_new[df_old.columns]

    print("3. 正在合并数据...")
    # ignore_index=True 非常重要，重新生成索引
    df_final = pd.concat([df_old, df_new], ignore_index=True)

    # ==========================================
    # 数据微调 (针对演示效果)
    # ==========================================
    # 假设你的 CSV 里的股票代码是 A，但你想在网页上点开 'B' 股票时看到数据
    # 你可以在这里强行改名 (如果不需要改，注释掉下面这行)
    # df_final['stock_id'] = '600519.SH'  # <--- 修改这里为你演示时想点开的那只股票代码

    print(f"4. 正在写入文件 (总计 {len(df_final)} 条)...")
    df_final.to_parquet(PARQUET_FILE, engine='pyarrow', index=False)
    print("✅ 成功！现在去运行你的网页吧。")

if __name__ == "__main__":
    merge_csv_to_parquet()