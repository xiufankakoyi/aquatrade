import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')

# 清除缓存
from server.routes.screener_data_service import ScreenerDataService
svc = ScreenerDataService()
svc.clear_cache()

# 测试
df = svc.get_data(date='2026-04-17', fields=None, conditions=None)
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
if not df.is_empty():
    sample = df.head(3).to_dicts()
    for row in sample:
        print(f"\n{row['stock_code']}:")
        print(f"  close: {row.get('close')}")
        print(f"  prev_close: {row.get('prev_close')}")
        print(f"  change_amount: {row.get('change_amount')}")
        print(f"  change_pct: {row.get('change_pct')}")
        print(f"  volume: {row.get('volume')}")
        print(f"  turnover_rate: {row.get('turnover_rate')}")