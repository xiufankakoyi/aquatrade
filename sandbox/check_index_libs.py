"""
检查并修复 ArcticDB 库
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
import shutil


def check_library_dirs():
    """检查库目录"""
    base_path = Path('data/arctic_db')
    
    index_libs = ['hs300_daily', 'sz50_daily', 'zz500_daily', 
                  'cyb_index_daily', 'sh_index_daily', 'sz_index_daily']
    
    print("=" * 70)
    print("检查指数库目录")
    print("=" * 70)
    
    for lib_name in index_libs:
        lib_path = base_path / lib_name
        
        if lib_path.exists():
            # 检查是否有实际数据
            has_data = False
            for item in lib_path.rglob('*.mdb'):
                if '_arctic_cfg' not in str(item) and item.stat().st_size > 10000:
                    has_data = True
                    break
            
            status = "✅ 有数据" if has_data else "📭 空库"
            print(f"{status} {lib_name}")
            
            # 列出目录结构
            for item in lib_path.iterdir():
                if item.is_dir():
                    print(f"    └── {item.name}/")
        else:
            print(f"❓ {lib_name} - 目录不存在")


def clean_empty_libraries():
    """清理空的库目录"""
    base_path = Path('data/arctic_db')
    
    index_libs = ['hs300_daily', 'sz50_daily', 'zz500_daily', 
                  'cyb_index_daily', 'sh_index_daily', 'sz_index_daily']
    
    print("\n" + "=" * 70)
    print("清理空库")
    print("=" * 70)
    
    for lib_name in index_libs:
        lib_path = base_path / lib_name
        
        if lib_path.exists():
            # 检查是否有实际数据
            has_data = False
            for item in lib_path.rglob('*.mdb'):
                if '_arctic_cfg' not in str(item) and item.stat().st_size > 10000:
                    has_data = True
                    break
            
            if not has_data:
                print(f"删除空库: {lib_name}")
                shutil.rmtree(lib_path)
            else:
                print(f"保留: {lib_name}")


if __name__ == '__main__':
    check_library_dirs()
    # clean_empty_libraries()  # 取消注释以清理空库
