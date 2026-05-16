"""
调试 symbol 转换问题
"""
import sys
sys.path.insert(0, '.')

from server.app import get_api
api = get_api()

# 测试 _normalize_symbol_code
symbol = '000300'
normalized = api._normalize_symbol_code(symbol)
print(f"Original: {symbol}")
print(f"Normalized: {normalized}")

# 测试 _get_index_kline_from_parquet 使用原始代码和规范化后的代码
print("\n=== Testing _get_index_kline_from_parquet ===")
result1 = api._get_index_kline_from_parquet('000300', '2024-01-01', '2024-12-31')
print(f"With '000300': {len(result1)} records")

result2 = api._get_index_kline_from_parquet(normalized, '2024-01-01', '2024-12-31')
print(f"With '{normalized}': {len(result2)} records")

# 检查 INDEX_MAPPING
INDEX_MAPPING = {
    '000300': 'hs300_daily.parquet',
    '000905': 'zz500_daily.parquet',
    '000001': 'sh_index_daily.parquet',
    '399001': 'sz_index_daily.parquet',
    '000016': 'sz50_daily.parquet',
    '399006': 'cyb_index_daily.parquet',
}
print(f"\nIs '{normalized}' in INDEX_MAPPING? {normalized in INDEX_MAPPING}")
print(f"Is '000300' in INDEX_MAPPING? {'000300' in INDEX_MAPPING}")
