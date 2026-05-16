"""
使用 REST API 方式插入缺失日期数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests
import pandas as pd
from datetime import datetime
from config.config import Config

print("=" * 70)
print("使用 REST API 填补缺失日期")
print("=" * 70)

# 1. 检查缺失日期
print("\n[1] 检查缺失日期...")
resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={"start_date": "2026-02-04", "end_date": "2026-02-14"},
    timeout=5
)
data = resp.json()
missing = data.get("missing_dates", [])
print(f"   缺失日期: {missing}")

if not missing:
    print("\n✅ 没有缺失日期！")
    exit(0)

target_date = missing[0]
target_date_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
print(f"\n[2] 目标日期: {target_date_fmt}")

# 2. 从 Tushare 获取数据
print(f"\n[3] 从 Tushare 获取数据...")
import tushare as ts
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

df_daily = pro.daily(trade_date=target_date)
if df_daily is None or df_daily.empty:
    print(f"   ❌ 没有数据")
    exit(1)

print(f"   ✅ 获取到 {len(df_daily)} 条数据")

# 3. 使用 QuestDB REST API 插入
print(f"\n[4] 使用 REST API 插入...")

# 构建 INSERT 语句
# QuestDB 的 INSERT 语法: INSERT INTO table VALUES (...)
insert_statements = []
for _, row in df_daily.iterrows():
    stock_code = row['ts_code'].split('.')[0]
    ts = f"{target_date_fmt}T00:00:00.000000Z"
    
    open_p = row.get('open', 0) or 0
    high = row.get('high', 0) or 0
    low = row.get('low', 0) or 0
    close = row.get('close', 0) or 0
    volume = row.get('vol', 0) or 0
    amount = row.get('amount', 0) or 0
    adj_factor = row.get('adj_factor', 1) or 1
    prev_close = row.get('pre_close', 0) or 0
    
    sql = f"""INSERT INTO base_daily VALUES(
        '{stock_code}', {open_p}, {high}, {low}, {close}, 
        {volume}, {amount}, {adj_factor}, {prev_close}, 
        '{ts}'
    )"""
    insert_statements.append(sql)

# 批量执行插入
success_count = 0
for i, sql in enumerate(insert_statements):
    try:
        resp = requests.get(
            'http://localhost:9000/exec',
            params={'query': sql},
            timeout=10
        )
        if resp.status_code == 200:
            success_count += 1
        else:
            print(f"   插入第 {i+1} 条失败: {resp.text[:100]}")
    except Exception as e:
        print(f"   插入第 {i+1} 条异常: {e}")
    
    if (i + 1) % 1000 == 0:
        print(f"   已插入 {i+1}/{len(insert_statements)} 条")

print(f"   ✅ 成功插入 {success_count}/{len(insert_statements)} 条")

# 5. 验证
print(f"\n[5] 验证...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': f"SELECT COUNT(*) FROM base_daily WHERE date_trunc('day', timestamp) = '{target_date_fmt}'"},
    timeout=5
)
data = resp.json()
if 'dataset' in data and data['dataset']:
    count = data['dataset'][0][0]
    print(f"   QuestDB 中数据条数: {count}")

# 6. 检查后端
resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={"start_date": target_date_fmt, "end_date": target_date_fmt},
    timeout=5
)
data = resp.json()
if target_date not in data.get("missing_dates", []):
    print(f"   ✅ {target_date_fmt} 不再缺失！")
else:
    print(f"   ❌ 仍然缺失")

print("=" * 70)
