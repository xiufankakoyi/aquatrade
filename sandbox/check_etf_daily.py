"""
检查是否有ETF日线交易数据
"""
import sys
sys.path.insert(0, '.')

from data_svc.storage.arcticdb_manager import get_arctic_instance

def check_etf_daily():
    print("检查ETF日线交易数据...")
    
    arctic = get_arctic_instance()
    libraries = arctic.list_libraries()
    print(f"可用库: {libraries}")
    
    # 检查是否有 fund_daily 库
    if 'fund_daily' in libraries:
        print("\n找到 fund_daily 库!")
        lib = arctic['fund_daily']
        symbols = lib.list_symbols()
        print(f"symbol数量: {len(symbols)}")
        
        # 检查513050
        etf_codes = ['513050.SH', '513050', '159605.SZ', '159605']
        for code in etf_codes:
            if code in symbols:
                print(f"\n找到 {code}:")
                data = lib.read(code)
                df = data.data
                print(df.tail(5)[['close']])
    else:
        print("\n没有 fund_daily 库")
    
    # 检查 daily 库中是否有ETF
    print("\n检查 daily 库中的ETF...")
    if 'daily' in libraries:
        lib = arctic['daily']
        symbols = lib.list_symbols()
        
        # ETF代码格式检查
        etf_patterns = ['513050', '159605', '510300', '510500', '159915']
        for pattern in etf_patterns:
            matches = [s for s in symbols if pattern in s]
            if matches:
                print(f"找到 {pattern}: {matches}")
                for m in matches:
                    data = lib.read(m)
                    df = data.data
                    print(f"  {m} 最新close: {df.iloc[-1]['close']}")

if __name__ == "__main__":
    check_etf_daily()
