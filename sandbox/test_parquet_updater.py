"""
直接测试 ParquetUpdater
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.logger import get_logger

logger = get_logger(__name__)

def test_progress_callback(data):
    """测试进度回调"""
    print(f"\n[Callback] 收到进度更新: {data}")

def main():
    print("=" * 80)
    print("测试 ParquetUpdater")
    print("=" * 80)
    
    try:
        from data_svc.database.parquet_updater import ParquetUpdater
        
        print("\n1. 创建 ParquetUpdater...")
        updater = ParquetUpdater(progress_callback=test_progress_callback)
        
        print("\n2. 获取最新日期...")
        last_date = updater.get_last_trade_date()
        print(f"   最新日期: {last_date}")
        
        print("\n3. 获取更新日期...")
        update_days = updater.get_update_days()
        print(f"   需要更新的日期: {update_days}")
        
        if not update_days:
            print("\n✅ 数据已是最新，无需更新")
            return
        
        print("\n4. 运行同步...")
        result = updater.run_sync()
        print(f"   同步结果: {result}")
        
        print("\n✅ 测试成功!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
