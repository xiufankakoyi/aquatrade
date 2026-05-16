import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')
from data_svc.ingestion.dragon_eye_adapter import DragonEyeAdapter
from data_svc.spiders.dragon_spider.main import is_trading_day
from datetime import datetime

adapter = DragonEyeAdapter()
missing = adapter._scan_missing_dates()
print(f'Missing dates: {len(missing)}')
print()

trading_missing = []
non_trading_missing = []
for d in missing:
    dt = datetime.strptime(d, '%Y-%m-%d')
    if is_trading_day(dt):
        trading_missing.append(d)
    else:
        non_trading_missing.append(d)

print(f'Trading days missing: {len(trading_missing)}')
print(f'  {trading_missing}')
print()
print(f'Non-trading days missing: {len(non_trading_missing)}')
print(f'  {non_trading_missing}')