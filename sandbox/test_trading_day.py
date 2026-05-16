import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')
from data_svc.spiders.dragon_spider.main import is_trading_day
from datetime import datetime

dates = [
    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20',
    '2026-02-23', '2026-02-24', '2026-02-25',
    '2026-04-20', '2026-04-21', '2026-04-22', '2026-04-23', '2026-04-24'
]

print('Trading day check:')
for d in dates:
    dt = datetime.strptime(d, '%Y-%m-%d')
    is_trade = is_trading_day(dt)
    status = 'TRADING' if is_trade else 'NON-TRADING'
    print(f'  {d}: {status}')