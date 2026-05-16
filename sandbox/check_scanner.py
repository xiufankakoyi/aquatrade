"""
检查 LanceDB table 是否有 scanner 方法
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from data_svc.storage.lancedb_reader import get_lancedb_reader

reader = get_lancedb_reader()
table = reader.table

print(f"table 类型: {type(table)}")
print(f"table 属性: {[a for a in dir(table) if not a.startswith('_')][:30]}")
print(f"has scanner: {hasattr(table, 'scanner')}")
print(f"has to_lance: {hasattr(table, 'to_lance')}")

# 尝试调用 scanner
if hasattr(table, 'scanner'):
    print("\n使用 scanner:")
    scanner = table.scanner(columns=['stock_code', 'trade_date'])
    print(f"  scanner: {scanner}")
    result = scanner.to_table()
    print(f"  result: {len(result)} 行")
