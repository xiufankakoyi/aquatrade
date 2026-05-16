"""验证后端 QuestDB 配置"""
import requests

print("=" * 60)
print("验证后端 QuestDB 配置")
print("=" * 60)

# 测试最后日期
try:
    resp = requests.get("http://localhost:5000/api/db/last_date", timeout=5)
    data = resp.json()
    print(f"最后日期: {data.get('last_date')}")
except Exception as e:
    print(f"后端连接失败: {e}")

# 测试缺失日期
try:
    resp = requests.get("http://localhost:5000/api/db/missing_dates?start_date=2026-02-11&end_date=2026-02-11", timeout=5)
    data = resp.json()
    missing = data.get("missing_dates", [])
    if "20260211" in missing:
        print("2026-02-11: 缺失")
    else:
        print("2026-02-11: 已存在")
except Exception as e:
    print(f"查询失败: {e}")

print("=" * 60)
