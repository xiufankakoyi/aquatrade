import requests
import json

resp = requests.post('http://localhost:5000/api/screener/filter', json={
    'page': 1,
    'pageSize': 5
})

print('Status:', resp.status_code)
data = resp.json()
print('Success:', data.get('success'))

if data.get('success') and data.get('data'):
    records = data['data'].get('records', [])
    print('返回', len(records), '条数据')
    if records:
        print()
        print('样本数据:')
        for item in records[:3]:
            print(f"  {item.get('stock_code')} {item.get('stock_name')}")
            print(f"    beta_60d: {item.get('beta_60d')}")
            print(f"    alpha_60d: {item.get('alpha_60d')}")
            print(f"    corr_60d: {item.get('corr_60d')}")
            print(f"    return_5d: {item.get('return_5d')}")
else:
    print('Error:', data.get('error'))
