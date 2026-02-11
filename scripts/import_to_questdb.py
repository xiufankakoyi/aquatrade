"""
QuestDB 数据导入脚本
====================
将拆分后的热数据 Parquet 文件导入到 QuestDB。

用法:
    python scripts/import_to_questdb.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from datetime import datetime
from data_svc.database.questdb_manager import get_questdb_manager

# 热数据文件路径
BASE_DIR = r"d:\aquatrade\data\parquet_data"
FILES = {
    "base": os.path.join(BASE_DIR, "base_daily_hot.parquet"),
    "momentum": os.path.join(BASE_DIR, "factors_momentum_hot.parquet"),
    "valuation": os.path.join(BASE_DIR, "factors_valuation_hot.parquet"),
}


def main():
    print("=" * 60)
    print("📊 QuestDB 数据导入工具")
    print("=" * 60)
    
    # 1. 检查 QuestDB 连接
    print("\n[1/5] 检查 QuestDB 连接...")
    qdb = get_questdb_manager()
    
    if not qdb.health_check():
        print("❌ 错误: QuestDB 未运行")
        print("   请先运行: start_questdb.bat")
        return False
    
    print("   ✓ QuestDB 运行正常")
    
    # 2. 创建表结构
    print("\n[2/5] 创建表结构...")
    try:
        results = qdb.create_tables()
        success_count = sum(1 for r in results if r.get("success", False))
        print(f"   ✓ 创建/检查 {success_count} 张表")
    except Exception as e:
        print(f"   ⚠️ 表可能已存在: {e}")
    
    # 3. 导入基础行情
    print("\n[3/5] 导入基础行情数据...")
    try:
        base_df = pl.read_parquet(FILES["base"])
        print(f"   读取 {len(base_df):,} 行")
        
        batch_size = 50000
        total = len(base_df)
        start_time = datetime.now()
        
        for i in range(0, total, batch_size):
            batch = base_df.slice(i, batch_size)
            qdb.insert_base_daily(batch)
            progress = min(100, (i + batch_size) * 100 // total)
            print(f"      进度: {progress}%", end="\r")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n   ✓ 完成 ({elapsed:.1f}s)")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 4. 导入动量因子
    print("\n[4/5] 导入动量因子...")
    try:
        momentum_df = pl.read_parquet(FILES["momentum"])
        print(f"   读取 {len(momentum_df):,} 行")
        
        start_time = datetime.now()
        for i in range(0, total, batch_size):
            batch = momentum_df.slice(i, batch_size)
            qdb.insert_factors_momentum(batch)
            progress = min(100, (i + batch_size) * 100 // total)
            print(f"      进度: {progress}%", end="\r")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n   ✓ 完成 ({elapsed:.1f}s)")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 5. 导入估值因子
    print("\n[5/5] 导入估值因子...")
    try:
        valuation_df = pl.read_parquet(FILES["valuation"])
        print(f"   读取 {len(valuation_df):,} 行")
        
        start_time = datetime.now()
        for i in range(0, total, batch_size):
            batch = valuation_df.slice(i, batch_size)
            qdb.insert_factors_valuation(batch)
            progress = min(100, (i + batch_size) * 100 // total)
            print(f"      进度: {progress}%", end="\r")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n   ✓ 完成 ({elapsed:.1f}s)")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 完成
    print("\n" + "=" * 60)
    print("✅ 数据导入完成!")
    print("=" * 60)
    print(f"\n访问 QuestDB Web UI: http://localhost:9000")
    print("\n示例查询:")
    print("  SELECT code, ts, close FROM base_daily LIMIT 10;")
    print("  SELECT code, rsi_14 FROM factors_momentum WHERE rsi_14 < 30;")
    
    qdb.close()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
