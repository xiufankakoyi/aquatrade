"""测试 Polars V3 加载器性能"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
from data_svc.database.polars_data_loader_v3 import get_polars_loader_v3

def test_v3_loader():
    """测试 V3 加载器"""
    print("\n" + "=" * 70)
    print("Polars V3 加载器性能测试")
    print("=" * 70)
    
    loader = get_polars_loader_v3()
    
    # 测试一年数据
    t_start = time.perf_counter()
    result = loader.load_period_to_matrix(
        start_date="2023-01-01",
        end_date="2023-12-31"
    )
    t_end = time.perf_counter()
    
    if result:
        print(f"\n加载成功!")
        print(f"  交易日数: {result['T']}")
        print(f"  股票数: {result['N']}")
        print(f"  总耗时: {(t_end - t_start)*1000:.1f}ms")
    else:
        print("加载失败!")

if __name__ == "__main__":
    test_v3_loader()
