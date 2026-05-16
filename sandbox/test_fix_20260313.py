import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
import polars as pl
from server.routes.screener_data_service import get_screener_service

svc = get_screener_service()
svc.clear_cache()
df = svc.get_data(date='2026-03-13', fields=None, conditions=None)
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"change_pct null count: {df.filter(pl.col('change_pct').is_null()).height}")
print(f"volume null count: {df.filter(pl.col('volume').is_null()).height}")
print("\n前3行数据:")
for row in df.head(3).to_dicts():
    print(f"  {row['stock_code']}: close={row.get('close')}, change_pct={row.get('change_pct')}, volume={row.get('volume')}")