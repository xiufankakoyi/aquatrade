# scripts/migrate_to_lancedb.py
"""
迁移脚本：将 Parquet 数据转换为 LanceDB

使用方法:
    python scripts/migrate_to_lancedb.py

环境变量:
    PARQUET_DIR: Parquet 数据目录（默认: parquet_data）
    LANCE_DIR: LanceDB 数据目录（默认: parquet_data/lance_db）
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.lance_manager import migrate_parquet_to_lance, LanceDBManager
from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)


def migrate_all_parquet_files():
    """迁移所有 Parquet 文件到 LanceDB"""
    print("=" * 60)
    print("LanceDB 完整迁移工具")
    print("=" * 60)
    
    parquet_dir = Config.PARQUET_DIR
    results = {}
    
    # 定义所有需要迁移的 Parquet 文件
    # 注意：benchmark_data 在 SQLite 中，需要先导出为 Parquet
    parquet_files = {
        "stock_daily": "stock_daily.parquet",
        "stock_info": "stock_info.parquet",
        "stock_limit_status": "stock_limit_status.parquet",
    }
    
    # 检查是否需要导出 benchmark_data
    benchmark_parquet = os.path.join(parquet_dir, "benchmark_daily.parquet")
    if os.path.exists(benchmark_parquet):
        parquet_files["benchmark_data"] = "benchmark_daily.parquet"
        print(f"\n✓ 找到 benchmark_daily.parquet，将包含在迁移中")
    else:
        print("\n⚠️  benchmark_daily.parquet 不存在")
        print("   如果需要迁移 benchmark 数据，请先运行:")
        print("   python scripts/export_benchmark.py")
    
    print(f"\n检查 Parquet 目录: {parquet_dir}")
    print("=" * 60)
    
    # 检查所有文件
    for table_name, filename in parquet_files.items():
        parquet_path = os.path.join(parquet_dir, filename)
        
        if not os.path.exists(parquet_path):
            print(f"⚠️  跳过: {filename} (文件不存在)")
            results[table_name] = {"status": "skipped", "reason": "文件不存在"}
            continue
        
        file_size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
        print(f"\n✓ 找到: {filename}")
        print(f"   大小: {file_size_mb:.2f} MB")
        print(f"   表名: {table_name}")
        
        try:
            # 执行迁移
            print(f"   开始迁移...")
            manager = migrate_parquet_to_lance(
                parquet_path=parquet_path,
                table_name=table_name
            )
            
            # 显示表信息
            info = manager.get_table_info()
            if info.get('exists'):
                print(f"   ✓ 迁移成功")
                print(f"     行数: {info.get('rows', 0):,}")
                if 'stock_count' in info:
                    print(f"     股票数: {info.get('stock_count', 0):,}")
                if 'date_range' in info and info['date_range']:
                    print(f"     日期范围: {info['date_range']}")
            
            results[table_name] = {"status": "success", "info": info}
            
        except Exception as e:
            print(f"   ❌ 迁移失败: {e}")
            results[table_name] = {"status": "failed", "error": str(e)}
            import traceback
            traceback.print_exc()
    
    # 总结
    print("\n" + "=" * 60)
    print("迁移总结")
    print("=" * 60)
    
    success_count = sum(1 for r in results.values() if r.get("status") == "success")
    failed_count = sum(1 for r in results.values() if r.get("status") == "failed")
    skipped_count = sum(1 for r in results.values() if r.get("status") == "skipped")
    
    print(f"成功: {success_count}")
    print(f"失败: {failed_count}")
    print(f"跳过: {skipped_count}")
    
    if success_count > 0:
        print("\n" + "=" * 60)
        print("下一步：")
        print("=" * 60)
        print("1. 设置环境变量: DB_BACKEND=lancedb")
        print("2. 重启回测服务")
        print("3. 享受极速回测！")
        print("=" * 60)
    
    return results


def main():
    """主函数：迁移所有 Parquet 到 LanceDB"""
    migrate_all_parquet_files()


if __name__ == "__main__":
    main()

