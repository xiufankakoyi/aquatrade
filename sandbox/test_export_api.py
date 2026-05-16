import requests

data = {
    'backtest_result': {
        'metrics': {
            'annualizedReturn': 10.5,
            'sharpeRatio': 1.2,
            'maxDrawdown': -15,
            'winRate': 0.6
        },
        'strategyInfo': {'name': '测试策略'}
    }
}

response = requests.post('http://localhost:5000/api/export/excel', json=data)
print(f'Status: {response.status_code}')
print(f'Content-Type: {response.headers.get("Content-Type")}')
if response.status_code == 200:
    with open('test_export.xlsx', 'wb') as f:
        f.write(response.content)
    print(f'File saved: {len(response.content)} bytes')
else:
    print(f'Error: {response.text}')
