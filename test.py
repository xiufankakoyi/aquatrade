import lancedb
import time
import os

# 配置路径
LANCE_DB_PATH = "./parquet_data/lance_db"
TABLE_NAME = "stock_daily"

def optimize_and_test():
    print("="*60)
    print(f"⚡ LanceDB 索引构建与最终性能测试")
    print("="*60)

    if not os.path.exists(LANCE_DB_PATH):
        print("❌ 数据库路径不存在")
        return

    db = lancedb.connect(LANCE_DB_PATH)
    if TABLE_NAME not in db.table_names():
        print(f"❌ 表 {TABLE_NAME} 不存在")
        return

    table = db.open_table(TABLE_NAME)
    row_count = table.count_rows()
    print(f"📊 当前数据量: {row_count:,} 行")

    # ---------------------------------------------------------
    # 步骤 1: 创建标量索引 (Scalar Index)
    # 这是让查询从 10秒 变成 0.01秒 的关键
    # ---------------------------------------------------------
    print("\n[步骤 1] 正在创建索引 (这可能需要几秒钟)...")
    
    start_idx = time.time()
    
    # 为 trade_date 创建索引 (加速日期查询)
    # 这里的 BTree 适合高基数数据（日期）
    try:
        print("   👉 正在为 'trade_date' 创建索引...")
        table.create_scalar_index("trade_date") 
        print("      ✓ trade_date 索引创建成功")
    except Exception as e:
        print(f"      ⚠️ 索引可能已存在或创建失败: {e}")

    # 为 stock_code 创建索引 (加速单股查询)
    try:
        print("   👉 正在为 'stock_code' 创建索引...")
        table.create_scalar_index("stock_code")
        print("      ✓ stock_code 索引创建成功")
    except Exception as e:
        print(f"      ⚠️ 索引可能已存在或创建失败: {e}")
        
    print(f"   ⏱️ 索引构建耗时: {time.time() - start_idx:.2f} 秒")

    # ---------------------------------------------------------
    # 步骤 2: 极限速度测试
    # ---------------------------------------------------------
    print("\n[步骤 2] 性能验证...")
    
    # 测试日期: 2000-01-04 (数据最早的一天)
    target_date = "2000-01-04" 
    print(f"   🎯 查询目标日期: {target_date}")
    
    # 第一次查询 (冷启动)
    start_q1 = time.time()
    res1 = table.search().where(f"trade_date = '{target_date}'").to_pandas()
    t1 = time.time() - start_q1
    print(f"   🚀 第一次查询耗时: {t1:.4f} 秒 (行数: {len(res1)})")

    # 第二次查询 (热缓存)
    start_q2 = time.time()
    res2 = table.search().where(f"trade_date = '{target_date}'").to_pandas()
    t2 = time.time() - start_q2
    print(f"   🔥 第二次查询耗时: {t2:.4f} 秒")

    # ---------------------------------------------------------
    # 结论判定
    # ---------------------------------------------------------
    print("\n" + "="*60)
    if t1 < 0.5:
        print("✅ 成功解决！性能已达标 (毫秒级响应)。")
        print("👉 现在可以安全重启后端服务了。")
    else:
        print("❌ 警告：性能依然未达标，可能需要检查 LanceDB 版本或数据类型。")
    print("="*60)

if __name__ == "__main__":
    optimize_and_test()