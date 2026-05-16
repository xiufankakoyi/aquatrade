import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import lancedb
import duckdb
from data_svc.storage.lancedb_reader import get_lancedb_reader

r = get_lancedb_reader()
db = lancedb.connect(r.db_path)
tbl = db.open_table('daily_ohlcv')

conn = duckdb.connect(database=':memory:')
scanner = tbl.to_lance().scanner()
arrow_table = scanner.to_table()
conn.register('dailies', arrow_table)

# 检查 2026-03-13 的数据
result = conn.execute("""
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_vol,
    SUM(CASE WHEN change_pct IS NULL THEN 1 ELSE 0 END) as null_chg,
    SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) as null_amt
FROM dailies
WHERE trade_date = date '2026-03-13'
""").fetchdf()

print("2026-03-13 数据检查:")
print(result.to_string())

# 检查 2026-04-17 的数据
result2 = conn.execute("""
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_vol,
    SUM(CASE WHEN change_pct IS NULL THEN 1 ELSE 0 END) as null_chg
FROM dailies
WHERE trade_date = date '2026-04-17'
""").fetchdf()

print("\n2026-04-17 数据检查:")
print(result2.to_string())

conn.close()