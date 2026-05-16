"""检查 QuestDB stock_daily 表的列名"""
import requests

QUESTDB_HOST = "localhost"
QUESTDB_PORT = 9000

def query(sql):
    try:
        response = requests.get(
            f"http://{QUESTDB_HOST}:{QUESTDB_PORT}/exec",
            params={"query": sql},
            timeout=30
        )
        print(f"SQL: {sql}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

print("=" * 70)
print("检查 QuestDB stock_daily 表结构")
print("=" * 70)

# 1. 检查列
print("\n[1] 检查 stock_daily 列:")
query("SHOW COLUMNS FROM stock_daily")

# 2. 尝试查询一行数据
print("\n[2] 尝试查询一行数据:")
query("SELECT * FROM stock_daily LIMIT 1")

# 3. 检查数据量
print("\n[3] 检查数据量:")
query("SELECT COUNT(*) FROM stock_daily")
