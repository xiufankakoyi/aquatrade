"""测试 Polars V5 加载器性能"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import time
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5

def test_v5_loader():
    """测试 V5 加载器"""
    print("\n" + "=" * 70)
    print("Polars V5 加载器性能测试（极简字段）")
    print("=" * 70)
    
    loader = get_polars_loader_v5()
    
    # 测试一年数据 - 只读取必要字段
    t_start = time.perf_counter()
    result = loader.load_period_to_matrix(
        start_date="2023-01-01",
        end_date="2023-12-31",
        required_fields=['open', 'high', 'low', 'close', 'volume']
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
    test_v5_loader()
