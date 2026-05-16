"""
测试中概互联ETF价格获取
"""
import sys
sys.path.insert(0, '.')

from data_svc.unified_data_query import UnifiedDataQueryAdapter

def test_etf_price():
    print("测试中概互联ETF价格获取...")
    
    adapter = UnifiedDataQueryAdapter()
    
    # 中概互联ETF可能的代码
    etf_codes = [
        "513050",  # 中概互联ETF (SH)
        "159605",  # 中概互联ETF (SZ)
        "513050.SH",
        "159605.SZ",
    ]
    
    prices = adapter.get_latest_prices(etf_codes)
    
    print("\n获取结果:")
    for code, price in prices.items():
        print(f"  {code}: {price}")
    
    # 直接从 ArcticDB 读取
    print("\n直接从 ArcticDB 读取...")
    from data_svc.storage.arcticdb_manager import get_arcticdb_manager
    
    manager = get_arcticdb_manager()
    
    for code in ["513050.SH", "159605.SZ"]:
        try:
            df = manager.read_data('daily', code)
            if not df.empty:
                print(f"\n{code} 最新数据:")
                print(df.tail(3)[['close']])
        except Exception as e:
            print(f"{code}: 读取失败 - {e}")
    
    # 检查基金净值库
    print("\n检查基金净值库...")
    try:
        df = manager.read_data('fund_nav', '513050.OF')
        if not df.empty:
            print(f"513050.OF 最新净值:")
            print(df.tail(3))
    except Exception as e:
        print(f"513050.OF: 读取失败 - {e}")

if __name__ == "__main__":
    test_etf_price()
