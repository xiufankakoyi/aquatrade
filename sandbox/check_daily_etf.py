"""
检查 daily 库中的ETF数据格式
"""
import sys
sys.path.insert(0, '.')

from data_svc.storage.arcticdb_manager import get_arctic_instance

def check_daily_etf():
    print("检查 daily 库中的ETF数据...")
    
    arctic = get_arctic_instance()
    lib = arctic['daily']
    symbols = lib.list_symbols()
    
    # ETF代码通常以51、15、58、16开头
    etf_prefixes = ['51', '15', '58', '16', '50', '52', '53', '54', '55', '56', '57', '59']
    
    etf_symbols = [s for s in symbols if any(s.startswith(p) for p in etf_prefixes)]
    print(f"可能的ETF symbol数量: {len(etf_symbols)}")
    print(f"前20个: {etf_symbols[:20]}")
    
    # 检查513050是否在daily库中
    if '513050.SH' in symbols:
        print("\n找到 513050.SH 在 daily 库中")
        data = lib.read('513050.SH')
        df = data.data
        print(df.tail(5)[['close']])
    else:
        print("\n513050.SH 不在 daily 库中")
    
    # 检查是否有其他格式的ETF数据
    print("\n检查包含 '513' 的 symbol:")
    related = [s for s in symbols if '513' in s]
    print(related[:10])
    
    print("\n检查包含 '159' 的 symbol:")
    related = [s for s in symbols if '159' in s]
    print(related[:10])

if __name__ == "__main__":
    check_daily_etf()
