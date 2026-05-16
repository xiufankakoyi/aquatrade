"""
检查 513050 在哪个市场
"""
import sys
sys.path.insert(0, '.')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic['daily']
symbols = lib.list_symbols()

# 检查 513050 的所有可能 symbol
code = '513050'
for suffix in ['.SH', '.SZ', '']:
    symbol = f"{code}{suffix}"
    if symbol in symbols:
        data = lib.read(symbol)
        df = data.data
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            print(f"找到 {symbol}: 最新价格={latest.get('close')}, 日期={latest.get('trade_date', latest.name)}")

# 搜索包含 513050 的 symbol
print("\n搜索包含 513050 的 symbol:")
for s in symbols:
    if '513050' in s:
        print(f"  {s}")
