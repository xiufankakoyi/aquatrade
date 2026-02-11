# scripts/migrate_min_data.py
"""
迁移脚本：将 CSV 分时数据转换为 LanceDB

使用方法:
    python scripts/migrate_min_data.py

功能:
    - 支持单个 CSV 文件或包含多个 CSV 的文件夹
    - 自动处理海量数据（16GB+），使用流式处理
    - 按 stock_code 物理排序，优化查询性能
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.lance_manager import LanceDBManager
from config.logger import get_logger

logger = get_logger(__name__)


def main():
    # 1. 设置路径 -> 指向包含多个 CSV 的文件夹
    # 例如 D:\data\min_data_folder\
    source_dir = r"D:\aquatrade\data\mins"  # <--- 修改这里为你的文件夹路径
    
    # 2. 初始化
    manager = LanceDBManager(table_name="stock_min_1m")
    
    # 3. 执行
    print(f"开始迁移目录: {source_dir}")
    try:
        manager.convert_csv_to_lance(source_dir)
        
        # 验证
        info = manager.get_table_info()
        print(f"迁移成功，总行数: {info.get('rows', 0):,}")
        
    except Exception as e:
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

