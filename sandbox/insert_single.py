"""
使用单条 INSERT 插入数据（最稳定的方式）
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
import time

print("=" * 70)
print("使用单条 INSERT 插入数据")
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

# 3. 准备数据
df_daily['stock_code'] = df_daily['ts_code'].str.split('.', expand=True)[0]

# 4. 逐条插入
print(f"\n[4] 逐条插入数据...")
success_count = 0
ts_str = target_date_fmt + "T00:00:00.000000Z"

for idx, row in df_daily.iterrows():
    try:
        insert_sql = f"""INSERT INTO base_daily 
            (stock_code, open, high, low, close, volume, amount, adj_factor, prev_close, timestamp) 
            VALUES (
                '{row['stock_code']}', 
                {row.get('open', 0) or 0}, 
                {row.get('high', 0) or 0}, 
                {row.get('low', 0) or 0}, 
                {row.get('close', 0) or 0}, 
                {row.get('vol', 0) or 0}, 
                {row.get('amount', 0) or 0}, 
                1.0, 
                {row.get('pre_close', 0) or 0}, 
                '{ts_str}'
            )"""
        
        resp = requests.get(
            'http://localhost:9000/exec',
            params={'query': insert_sql},
            timeout=10
        )
        
        if resp.status_code == 200:
            success_count += 1
        else:
            print(f"   第 {idx+1} 条失败: {resp.text[:100]}")
            break
            
        if (idx + 1) % 500 == 0:
            print(f"   已插入 {idx+1}/{len(df_daily)} 条")
            time.sleep(0.5)  # 稍微延迟避免过载
            
    except Exception as e:
        print(f"   第 {idx+1} 条异常: {e}")
        break

print(f"   ✅ 成功插入 {success_count} 条记录")

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
    if count > 0:
        print(f"   ✅ 数据插入成功！")

# 6. 检查后端 API
print(f"\n[6] 检查后端 API...")
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
