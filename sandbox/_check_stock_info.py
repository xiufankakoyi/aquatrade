import sys
sys.path.insert(0, '.')
import lancedb

db = lancedb.connect('data/lancedb')
result = db.list_tables()
tables = result.tables if hasattr(result, 'tables') else list(result)
print(f"Tables: {tables}")

if 'stock_info' in tables:
    t = db.open_table('stock_info')
    print(f"\nstock_info: {t.count_rows()} rows")
    print(f"Columns: {list(t.schema.names)}")
    ds = t.to_lance()
    scanner = ds.scanner()
    table = scanner.to_table()
    import polars as pl
    df = pl.from_arrow(table)
    print(df.head(5))
