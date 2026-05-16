import sys, requests
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')
from data_svc.spiders.dragon_spider.main import load_config

config = load_config()
token = config.get('TOKEN', '')
headers = {'Authorization': f'Bearer {token}'}

# 2026年春节: 2月17-23日放假，2月16日(周一)应该是最后一个交易日
# 测试2月及4月关键日期
test_dates = [
    ('2026-02-16', '春节前最后交易日?'),
    ('2026-02-24', '春节后第一个交易日?'),
    ('2026-02-25',),
    ('2026-02-26',),
    ('2026-03-02',),
    ('2026-04-06', '清明后第一个交易日?'),
    ('2026-04-07',),
    ('2026-04-20',),
    ('2026-04-21',),
    ('2026-04-22',),
    ('2026-04-23',),
]

print(f"Token: {token[:20]}..." if token else "NO TOKEN!")
print()
for item in test_dates:
    d = item[0]
    note = item[1] if len(item) > 1 else ''
    nodash = d.replace('-', '')
    url = f'https://stock.quicktiny.cn/api/limit-up/filter?date={nodash}&reasonTypeInput=&page=1&limit=3'
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            stocks = r.json().get('stocks', [])
            print(f'{d} [{r.status_code}] stocks={len(stocks)} {note}')
        else:
            print(f'{d} [{r.status_code}] {note}')
    except Exception as e:
        print(f'{d} ERROR: {e}')