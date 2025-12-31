import lancedb
import polars as pl
import pyarrow as pa
import time
import os

# 配置路径
LANCE_DB_PATH = "./parquet_data/lance_db"
TABLE_NAME = "stock_daily"

def fix_schema_and_finalize():
    print("="*60)
    print(f"🚑 LanceDB 类型修复与最终索引 (Schema Fix)")
    print("="*60)

    if not os.path.exists(LANCE_DB_PATH):
        print("❌ 数据库路径不存在")
        return

    db = lancedb.connect(LANCE_DB_PATH)
    
    # ---------------------------------------------------------
    # 步骤 1: 读取现有的“大字符串”数据
    # ---------------------------------------------------------
    print("\n[步骤 1] 读取数据并修正类型...")
    start_load = time.time()
    
    # 打开现有表（即使没有索引，数据本身是好的）
    table = db.open_table(TABLE_NAME)
    
    # 读取为 PyArrow 表
    arrow_table = table.to_arrow()
    
    # === 关键修复：强制转换 Schema ===
    # 将 LargeUtf8 (Polars默认) 转换为 Utf8 (LanceDB索引兼容)
    new_fields = []
    for field in arrow_table.schema:
        if field.name in ['trade_date', 'stock_code']:
            # 强制指定为标准 string (Utf8)
            print(f"   🔧 正在转换列: {field.name} (LargeUtf8 -> Utf8)...")
            new_fields.append(pa.field(field.name, pa.string()))
        else:
            new_fields.append(field)
            
    # 执行类型转换 (Cast)
    fixed_table = arrow_table.cast(pa.schema(new_fields))
    
    print(f"   📊 转换完成: {fixed_table.num_rows:,} 行 (耗时: {time.time() - start_load:.2f}s)")

    # ---------------------------------------------------------
    # 步骤 2: 覆盖写入 (Overwrite)
    # ---------------------------------------------------------
    print("\n[步骤 2] 覆盖写入修正后的数据...")
    start_write = time.time()
    
    # 覆盖写入 (这次是兼容索引的标准字符串类型)
    db.create_table(TABLE_NAME, fixed_table, mode="overwrite")
    
    print(f"   💾 写入完成 (耗时: {time.time() - start_write:.2f}s)")
    
    # 重新打开
    new_table = db.open_table(TABLE_NAME)

    # ---------------------------------------------------------
    # 步骤 3: 终于可以建索引了！
    # ---------------------------------------------------------
    print("\n[步骤 3] 创建索引 (这次一定会成功)...")
    start_idx = time.time()
    
    # 创建 trade_date 索引
    new_table.create_scalar_index("trade_date", replace=True)
    print("   ✓ 'trade_date' 索引创建成功")
    
    # 创建 stock_code 索引
    new_table.create_scalar_index("stock_code", replace=True)
    print("   ✓ 'stock_code' 索引创建成功")
    
    print(f"   ⚡ 索引构建耗时: {time.time() - start_idx:.2f}s")

    # ---------------------------------------------------------
    # 步骤 4: 最终极速验证
    # ---------------------------------------------------------
    print("\n[步骤 4] 见证奇迹 (查询 2000-01-04)...")
    target_date = "2000-01-04"
    
    # 预热
    new_table.search().where(f"trade_date = '{target_date}'").to_arrow()
    
    total_time = 0
    for i in range(10):
        t = time.time()
        # 纯 IO 测试
        _ = new_table.search().where(f"trade_date = '{target_date}'").to_arrow()
        total_time += (time.time() - t)
    
    avg_time = total_time / 10
    print(f"   🔥 平均查询耗时: {avg_time:.5f} 秒")
    
    if avg_time < 0.1:
        print("\n✅ 完美解决！这是物理极限速度。")
        print("   👉 马上启动后端，别犹豫了！")
    else:
        print(f"\n⚠️ 速度 {avg_time:.5f}s。虽然比 54s 快，但还没到极致。")

if __name__ == "__main__":
    fix_schema_and_finalize()