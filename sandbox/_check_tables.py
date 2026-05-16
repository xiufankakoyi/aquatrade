import sys
sys.path.insert(0, '.')
import lancedb

db = lancedb.connect('data/lancedb')
for name in db.table_names():
    t = db.open_table(name)
    print(f'{name}: {t.count_rows()} rows')
    print(f'  Columns: {list(t.schema.names)}')
    print()
