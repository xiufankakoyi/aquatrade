"""测试 Polars 数据加载器性能"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
from data_svc.database.polars_data_loader import get_polars_loader

def test_polars_loader():
    """测试 Polars 加载器"""
    print("\n" + "=" * 70)
    print("Polars 数据加载器性能测试")
    print("=" * 70)
    
    loader = get_polars_loader()
    
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
        print(f"\n矩阵字段:")
        for field, matrix in result['matrices'].items():
            print(f"  {field}: shape={matrix.shape}, dtype={matrix.dtype}")
    else:
        print("加载失败!")

if __name__ == "__main__":
    test_polars_loader()
