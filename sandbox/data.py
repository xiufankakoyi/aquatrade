import sys
import os
import time
from pathlib import Path

# --- 【关键修改】在导入任何重型库之前，强行把临时目录改到 D 盘 ---
temp_dir = r"D:\temp_polars"
os.makedirs(temp_dir, exist_ok=True)

print(f"🔒 正在锁定临时目录到: {temp_dir}")
os.environ["TEMP"] = temp_dir
os.environ["TMP"] = temp_dir
os.environ["POLARS_TEMP_DIR"] = temp_dir
# -------------------------------------------------------------

# 路径黑魔法
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.lance_manager import LanceDBManager

def build_index():
    print("="*40)
    print("🚀 开始为 14.5 亿行数据建立索引")
    print("   (缓存已强制重定向到 D 盘，C 盘安全)")
    print("="*40)
    
    mgr = LanceDBManager(table_name="stock_min_1m")
    table = mgr.db.open_table("stock_min_1m")
    
    print(f"[1] 当前行数: {table.count_rows():,}")
    print("[2] 正在为 'stock_code' 列建立标量索引 (Scalar Index)...")
    print("    (这一步需要大量读写 D 盘，请耐心等待 5-15 分钟)")
    
    t0 = time.time()
    try:
        # 强制创建标量索引
        table.create_scalar_index("stock_code")
        
        # 如果你想让按时间过滤也飞快，可以把下面这行解开
        # table.create_scalar_index("trade_time") 
        
        print(f"\n✅ 索引建立完成！耗时: {time.time() - t0:.2f}秒")
        print("现在查询应该已经是毫秒级了。")
        
    except Exception as e:
        print(f"\n❌ 建立索引失败: {e}")
        if "already exists" in str(e):
            print("提示：索引可能已经存在，无需重复建立。")

if __name__ == "__main__":
    build_index()