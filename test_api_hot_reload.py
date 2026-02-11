"""
测试热重载 API 端点
"""
import requests
import json

API_BASE = "http://localhost:5000/api/strategies"

print("="*60)
print("测试热重载 API 端点")
print("="*60)

# 测试 1: 获取配置
print("\n1. 获取策略配置")
try:
    resp = requests.get(f"{API_BASE}/jq_volume_v1pro/config")
    print(f"   状态码: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        print(f"   ✅ 成功: {data.get('success')}")
        print(f"   配置参数数量: {len(data.get('data', {}))}")
    else:
        print(f"   ❌ 失败: {resp.text}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

# 测试 2: 更新配置
print("\n2. 更新策略配置（热重载）")
try:
    new_config = {
        "market_cap_min": 300000,  # 修改为30-60亿
        "market_cap_max": 600000,
        "volume_ratio_threshold": 4.0,  # 修改量比阈值
        "ma_days": 5,
        "min_list_days": 60,
        "max_candidates": 1500,
        "position_ratio": 0.2,
        "max_stocks_per_day": 5
    }
    
    resp = requests.put(
        f"{API_BASE}/jq_volume_v1pro/config",
        json=new_config,
        headers={'Content-Type': 'application/json'}
    )
    print(f"   状态码: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        print(f"   ✅ 成功: {data.get('success')}")
        print(f"   消息: {data.get('message')}")
    else:
        print(f"   ❌ 失败: {resp.text}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

# 测试 3: 手动重载
print("\n3. 手动触发重载")
try:
    resp = requests.post(f"{API_BASE}/jq_volume_v1pro/reload")
    print(f"   状态码: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        print(f"   ✅ 成功: {data.get('success')}")
        print(f"   消息: {data.get('message')}")
    else:
        print(f"   ❌ 失败: {resp.text}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

# 测试 4: 列出所有配置
print("\n4. 列出所有配置文件")
try:
    resp = requests.get(f"{API_BASE}/configs/list")
    print(f"   状态码: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        print(f"   ✅ 成功: {data.get('success')}")
        print(f"   配置数量: {data.get('count')}")
        print(f"   配置列表: {data.get('data')}")
    else:
        print(f"   ❌ 失败: {resp.text}")
except Exception as e:
    print(f"   ❌ 错误: {e}")

print("\n" + "="*60)
print("API 测试完成")
print("="*60)
print("\n⚠️  注意：需要先启动服务器才能测试API")
print("启动命令: granian --interface asgi server.asgi_entry:asgi_app --host 0.0.0.0 --port 5000")
