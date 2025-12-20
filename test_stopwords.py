import pandas as pd
import duckdb
import os

# ==========================================
# 👇 这里改成你实际的一个 parquet 文件路径
# (随便找一个你数据库里的文件即可)
file_path = r"parquet_data/stock_daily.parquet" 
# ==========================================

def check_parquet_metadata(path):
    if not os.path.exists(path):
        print(f"❌ 错误：找不到文件: {path}")
        print("💡 提示：请修改脚本中的 file_path 变量为你本地存在的 Parquet 文件路径")
        return

    print(f"\n🔍 正在检查文件: {path}")
    print("=" * 50)

    # --- 方法 1: 使用 Pandas 查看列名和类型 ---
    print("\n[1] 字段列表 (Pandas Schema):")
    try:
        # 只读取 Schema，不读取数据，速度极快
        df = pd.read_parquet(path) 
        print(f"总共有 {len(df.columns)} 个字段")
        
        # 打印详细信息
        print(f"{'字段名':<25} | {'数据类型':<15}")
        print("-" * 45)
        for col in df.columns:
            dtype = str(df[col].dtype)
            print(f"{col:<25} | {dtype:<15}")
            
        # 重点检查刚才报错的字段
        missing_targets = ['ma60', 'is_limit_up', 'is_limit_down', 'is_st']
        print("-" * 45)
        print("🚩 重点缺失检查:")
        for target in missing_targets:
            if target in df.columns:
                print(f"  ✅ {target}: 存在")
            else:
                print(f"  ❌ {target}: 缺失 (会导致报错)")

    except Exception as e:
        print(f"Pandas 读取失败: {e}")

    # --- 方法 2: 使用 DuckDB 模拟查询 (最接近你报错的环境) ---
    print("\n" + "=" * 50)
    print("[2] DuckDB 预览 (前 5 行数据):")
    try:
        # 直接用 SQL 查询 Parquet
        rel = duckdb.sql(f"SELECT * FROM '{path}' LIMIT 5")
        rel.show()
    except Exception as e:
        print(f"DuckDB 读取失败: {e}")

if __name__ == "__main__":
    # 如果不知道文件名，这行代码会列出 database 目录下第一个找到的 parquet
    # 你可以把这段取消注释来自动查找文件
    # for root, dirs, files in os.walk("."):
    #     for file in files:
    #         if file.endswith(".parquet"):
    #             file_path = os.path.join(root, file)
    #             break
    
    check_parquet_metadata(file_path)