"""
测试ETF价格获取修复
"""
import sys
sys.path.insert(0, '.')

from data_svc.unified_data_query import UnifiedDataQueryAdapter

def test_etf_price_fix():
    print("测试ETF价格获取修复...")
    
    adapter = UnifiedDataQueryAdapter()
    
    # 测试中概互联ETF
    etf_codes = ["513050", "159605"]
    
    print("\n获取ETF交易价格:")
    prices = adapter.get_latest_prices(etf_codes)
    
    for code, price in prices.items():
        print(f"  {code}: {price}")
    
    # 测试普通股票
    print("\n获取普通股票价格:")
    stock_codes = ["600519", "000001"]
    prices = adapter.get_latest_prices(stock_codes)
    
    for code, price in prices.items():
        print(f"  {code}: {price}")

if __name__ == "__main__":
    test_etf_price_fix()
