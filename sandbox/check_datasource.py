"""
验证 QuestDB 数据源使用情况
"""
import requests
import json

BACKEND_URL = "http://localhost:5000"
QUESTDB_URL = "http://localhost:9000"

print("=== 检查数据源配置 ===")

# 检查 QuestDB 数据量
resp = requests.get(f"{QUESTDB_URL}/exec", params={"query": "SELECT COUNT(*) as cnt FROM base_daily"})
if resp.status_code == 200:
    count = resp.json().get('dataset', [[0]])[0][0]
    print(f"QuestDB base_daily: {count:,} 行")

# 检查日期范围
resp = requests.get(f"{QUESTDB_URL}/exec", params={"query": "SELECT MIN(ts), MAX(ts) FROM base_daily"})
if resp.status_code == 200:
    result = resp.json().get('dataset', [['N/A', 'N/A']])[0]
    print(f"QuestDB 日期范围: {result[0]} ~ {result[1]}")

# 检查股票数量
resp = requests.get(f"{QUESTDB_URL}/exec", params={"query": "SELECT COUNT(DISTINCT code) FROM base_daily"})
if resp.status_code == 200:
    count = resp.json().get('dataset', [[0]])[0][0]
    print(f"QuestDB 股票数量: {count}")

# 检查 2024-01-01 到 2024-03-31 的数据
resp = requests.get(f"{QUESTDB_URL}/exec", params={"query": """
    SELECT COUNT(*) as cnt FROM base_daily 
    WHERE ts >= '2024-01-01' AND ts <= '2024-03-31'
"""})
if resp.status_code == 200:
    count = resp.json().get('dataset', [[0]])[0][0]
    print(f"QuestDB 2024Q1 数据: {count:,} 行")

# 检查后端配置
print("\n=== 后端配置 ===")
try:
    resp = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
    print(f"后端状态: {resp.status_code}")
except Exception as e:
    print(f"后端错误: {e}")

# 运行一个简单回测并检查数据源
print("\n=== 运行简单回测测试 ===")

# 使用一个更简单的策略
payload = {
    "strategy_name": "simple_test",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
}

try:
    resp = requests.post(f"{BACKEND_URL}/api/run_backtest", json=payload, timeout=300)
    if resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            data = result.get('data', {})
            metrics = data.get('metrics', {})
            print(f"回测成功!")
            print(f"  总交易: {metrics.get('totalTrades', 0)}")
            print(f"  总收益: {metrics.get('totalReturn', 0):.2f}%")
        else:
            print(f"回测失败: {result.get('error', 'Unknown')}")
    else:
        print(f"请求失败: {resp.status_code}")
except Exception as e:
    print(f"错误: {e}")
