"""调试日期识别问题"""
import requests

print("=" * 60)
print("调试日期识别问题")
print("=" * 60)

# 1. 直接查询 QuestDB 中的所有日期
print("\n[1] QuestDB 中的日期:")
resp = requests.get(
    "http://localhost:9000/exec",
    params={"query": "SELECT date_trunc('day', timestamp) as date, COUNT(*) as cnt FROM base_daily GROUP BY date ORDER BY date"},
    timeout=5
)
data = resp.json()
if "dataset" in data:
    for row in data["dataset"]:
        print(f"  {row[0]}: {row[1]} 条")

# 2. 检查 2026-02-04 的数据
print("\n[2] 2026-02-04 的数据:")
resp = requests.get(
    "http://localhost:9000/exec",
    params={"query": "SELECT COUNT(*) FROM base_daily WHERE timestamp >= '2026-02-04T00:00:00.000Z' AND timestamp < '2026-02-05T00:00:00.000Z'"},
    timeout=5
)
data = resp.json()
if "dataset" in data:
    print(f"  2026-02-04 (UTC 范围): {data['dataset'][0][0]} 条")

# 3. 检查时间戳范围
print("\n[3] 时间戳范围:")
resp = requests.get(
    "http://localhost:9000/exec",
    params={"query": "SELECT MIN(timestamp), MAX(timestamp) FROM base_daily"},
    timeout=5
)
data = resp.json()
if "dataset" in data:
    print(f"  最小: {data['dataset'][0][0]}")
    print(f"  最大: {data['dataset'][0][1]}")

# 4. 检查后端 API 返回的缺失日期
print("\n[4] 后端 API 返回的缺失日期:")
resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={"start_date": "2026-02-04", "end_date": "2026-02-04"},
    timeout=5
)
data = resp.json()
print(f"  缺失日期: {data.get('missing_dates', [])}")

print("=" * 60)
