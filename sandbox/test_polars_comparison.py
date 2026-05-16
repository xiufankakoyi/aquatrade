"""对比 Polars V1 和 V2 的性能"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
from data_svc.database.polars_data_loader import get_polars_loader
from data_svc.database.polars_data_loader_v2 import get_polars_loader_v2

def test_comparison():
    """对比两个版本的性能"""
    print("\n" + "=" * 70)
    print("Polars 加载器性能对比")
    print("=" * 70)
    
    loader_v1 = get_polars_loader()
    loader_v2 = get_polars_loader_v2()
    
    # 测试 V1（使用 Pandas 转换）
    print("\n--- V1 (使用 Pandas 转换) ---")
    t_start = time.perf_counter()
    result_v1 = loader_v1.load_period_to_matrix(
        start_date="2023-01-01",
        end_date="2023-12-31"
    )
    t_v1 = (time.perf_counter() - t_start) * 1000
    print(f"V1 总耗时: {t_v1:.1f}ms")
    
    # 测试 V2（纯 Polars，无 Pandas）
    print("\n--- V2 (纯 Polars，无 Pandas) ---")
    t_start = time.perf_counter()
    result_v2 = loader_v2.load_period_to_matrix(
        start_date="2023-01-01",
        end_date="2023-12-31"
    )
    t_v2 = (time.perf_counter() - t_start) * 1000
    print(f"V2 总耗时: {t_v2:.1f}ms")
    
    # 对比结果
    print("\n" + "=" * 70)
    print("对比结果:")
    print(f"  V1 (Pandas): {t_v1:.1f}ms")
    print(f"  V2 (纯 Polars): {t_v2:.1f}ms")
    if t_v1 > t_v2:
        print(f"  V2 比 V1 快: {t_v1/t_v2:.2f}x")
    else:
        print(f"  V1 比 V2 快: {t_v2/t_v1:.2f}x")
    print("=" * 70)

if __name__ == "__main__":
    test_comparison()
