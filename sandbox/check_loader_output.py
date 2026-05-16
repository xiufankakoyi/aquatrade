"""
检查数据加载器的输出
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5

def check_loader():
    """检查加载器返回的股票代码"""
    print("检查数据加载器输出...")
    
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2023-01-01",
        "2023-01-31",
        required_fields=['open', 'close']
    )
    
    if matrix_data is None:
        print("❌ 加载失败")
        return
    
    stock_codes = matrix_data['stock_codes']
    
    print(f"\n股票代码列表信息:")
    print(f"  数量: {len(stock_codes)}")
    print(f"  类型: {type(stock_codes)}")
    
    print(f"\n前20个股票代码:")
    for i, code in enumerate(stock_codes[:20]):
        print(f"  {i}: {code} (类型: {type(code)})")

if __name__ == "__main__":
    check_loader()
