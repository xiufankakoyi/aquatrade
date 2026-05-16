"""
检查 QuestDB 表的实际列名
"""
import requests

print("=" * 80)
print("检查 QuestDB base_daily 表结构")
print("=" * 80)

# 查询表结构
try:
    resp = requests.get(
        'http://localhost:9000/exec',
        params={'query': "SELECT * FROM base_daily LIMIT 0"},
        timeout=5
    )
    if resp.status_code == 200:
        data = resp.json()
        if 'columns' in data:
            print("\nbase_daily 表的列:")
            for col in data['columns']:
                print(f"  - {col['name']}: {col['type']}")
        else:
            print("\n无法获取列信息")
            print(f"响应: {data}")
    else:
        print(f"查询失败: {resp.status_code}")
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 80)
