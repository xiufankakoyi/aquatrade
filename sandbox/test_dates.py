import sys, requests
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')
from data_svc.spiders.dragon_spider.main import load_config

config = load_config()
token = config.get('TOKEN', '')
headers = {'Authorization': f'Bearer {token}'}

dates_to_test = [
    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20',
    '2026-03-02', '2026-03-03', '2026-03-10',
    '2026-04-20', '2026-04-21', '2026-04-22', '2026-04-23',
]

print(f"Token: {token[:20]}..." if token else "No token!")
print()

for d in dates_to_test:
    nodash = d.replace('-', '')
    url = f'https://stock.quicktiny.cn/api/limit-up/filter?date={nodash}&reasonTypeInput=&page=1&limit=5'
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            stocks = data.get('stocks', [])
            print(f'{d} -> HTTP 200 | stocks: {len(stocks)}')
        else:
            print(f'{d} -> HTTP {r.status_code}')
    except Exception as e:
        print(f'{d} -> ERROR: {e}')