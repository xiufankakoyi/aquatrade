"""
检查 QuestDB 中的所有数据
"""
import requests

print("=" * 80)
print("检查 QuestDB 数据")
print("=" * 80)

# 查询总条数
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT COUNT(*) FROM base_daily"},
    timeout=5
)

data = resp.json()
print(f"\n总数据条数: {data}")

if 'dataset' in data and data['dataset']:
    count = data['dataset'][0][0]
    print(f"base_daily 表总条数: {count}")

# 查询所有日期
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT DISTINCT date_trunc('day', timestamp) as date FROM base_daily ORDER BY date"},
    timeout=5
)

data = resp.json()
print(f"\n所有日期:")
if 'dataset' in data:
    for row in data['dataset']:
        print(f"  {row[0]}")
else:
    print(f"  查询结果: {data}")

# 查询最近的数据
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT stock_code, open, close, timestamp FROM base_daily LIMIT 5"},
    timeout=5
)

data = resp.json()
print(f"\n样本数据:")
if 'dataset' in data:
    for row in data['dataset']:
        print(f"  {row}")
else:
    print(f"  查询结果: {data}")

print("\n" + "=" * 80)
