"""测试插入数据并验证"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from datetime import datetime, timezone
from config.config import Config
import requests

target_date = "20260204"
print("=" * 60)
print(f"测试插入 {target_date} 数据")
print("=" * 60)

# 1. 获取数据
import tushare as ts
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

df_daily = pro.daily(trade_date=target_date)
if df_daily is None or df_daily.empty:
    print(f"{target_date} 没有数据")
    exit(0)

print(f"获取到 {len(df_daily)} 条数据")

# 2. 插入数据 - 使用正确的时间戳格式
from questdb.ingress import Sender

df_daily["stock_code"] = df_daily["ts_code"].str.split(".", expand=True)[0]

# 使用 UTC 时间
ts_utc = datetime(2026, 2, 4, 0, 0, 0, tzinfo=timezone.utc)
print(f"使用时间戳: {ts_utc}")

records = 0
errors = []

try:
    with Sender("tcp", "localhost", 9009) as sender:
        for _, row in df_daily.iterrows():
            try:
                columns = {
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": float(row.get("vol", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                    "adj_factor": float(row.get("adj_factor", 1) or 1),
                    "prev_close": float(row.get("pre_close", 0) or 0),
                }
                
                sender.row(
                    "base_daily",
                    symbols={"stock_code": row["stock_code"]},
                    columns=columns,
                    at=ts_utc
                )
                records += 1
            except Exception as e:
                errors.append(str(e))
        
        sender.flush()
    
    print(f"插入完成: {records} 条")
    if errors:
        print(f"错误: {errors[:5]}")
        
except Exception as e:
    print(f"Sender 错误: {e}")
    import traceback
    traceback.print_exc()

# 3. 立即验证
print("\n验证数据...")
import time
time.sleep(2)  # 等待数据写入

resp = requests.get(
    "http://localhost:9000/exec",
    params={"query": f"SELECT COUNT(*) FROM base_daily WHERE timestamp >= '2026-02-04T00:00:00.000Z' AND timestamp < '2026-02-05T00:00:00.000Z'"}
)
print(f"   查询结果: {resp.text}")

# 4. 验证后端 API
print("\n验证后端 API...")
try:
    resp = requests.get('http://localhost:5000/api/db/last_date', timeout=5)
    data = resp.json()
    print(f"   后端最新日期: {data.get('last_date')}")
except Exception as e:
    print(f"   后端查询失败: {e}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)