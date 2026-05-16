"""
诊断预加载数据格式
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'INFO'

import polars as pl


def test_preloaded_data():
    """测试预加载数据格式"""
    print("\n" + "=" * 80)
    print("诊断预加载数据格式")
    print("=" * 80)
    
    from data_svc.unified_data_manager import get_unified_manager
    
    print("\n[1] 初始化并预加载数据...")
    manager = get_unified_manager()
    preloaded = manager.preload_to_memory(start_date="2024-01-01", end_date="2025-12-31")
    
    print(f"\n[2] 检查预加载数据格式...")
    for lib, df in preloaded.items():
        print(f"\n{lib}:")
        print(f"  行数: {len(df)}")
        print(f"  列: {df.columns}")
        print(f"  前3行:\n{df.head(3)}")
    
    print("\n[3] 测试 get_preloaded_data...")
    test_data = manager.get_preloaded_data("2024-01-01", "2024-01-31")
    for lib, df in test_data.items():
        print(f"\n{lib}:")
        print(f"  行数: {len(df)}")
        print(f"  列: {df.columns}")
        print(f"  前3行:\n{df.head(3)}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_preloaded_data()
