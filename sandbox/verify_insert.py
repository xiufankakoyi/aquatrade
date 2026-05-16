"""
验证数据是否成功插入
"""
import requests

print("=" * 80)
print("验证 2026-02-11 数据插入")
print("=" * 80)

# 查询数据条数
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': "SELECT COUNT(*) FROM base_daily WHERE date_trunc('day', timestamp) = '2026-02-11'"},
    timeout=5
)

data = resp.json()
print(f"\n响应: {data}")

if 'dataset' in data and data['dataset']:
    count = data['dataset'][0][0]
    print(f"2026-02-11 数据条数: {count}")
    
    # 查询样本数据
    resp = requests.get(
        'http://localhost:9000/exec',
        params={'query': "SELECT stock_code, open, close, volume, timestamp FROM base_daily WHERE date_trunc('day', timestamp) = '2026-02-11' LIMIT 5"},
        timeout=5
    )
    
    sample_data = resp.json()
    if 'dataset' in sample_data:
        print("\n样本数据:")
        for row in sample_data['dataset']:
            print(f"  {row}")
    
    print("\n" + "=" * 80)
    if count > 0:
        print("✅ 数据验证成功！")
    else:
        print("❌ 数据未找到")
else:
    print(f"❌ 查询失败: {data.get('error', '未知错误')}")

print("=" * 80)
