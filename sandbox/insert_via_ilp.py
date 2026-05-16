"""
使用 Influx Line Protocol (ILP) 方式插入数据
这是 QuestDB 推荐的高效插入方式
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import socket
import requests
import pandas as pd
from datetime import datetime
from config.config import Config

print("=" * 70)
print("使用 ILP 协议插入数据")
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

# 3. 使用 TCP socket 直接发送 ILP 数据
print(f"\n[4] 使用 ILP 协议插入...")

# 构建 ILP 数据行
# 格式: table_name,symbol=value field=value,field=value timestamp
ilp_lines = []
for _, row in df_daily.iterrows():
    stock_code = row['ts_code'].split('.')[0]
    
    # 时间戳转换为纳秒 (QuestDB 使用纳秒时间戳)
    ts = pd.to_datetime(target_date, format='%Y%m%d')
    ts_nanos = int(ts.timestamp() * 1_000_000_000)
    
    # 构建 ILP 行
    # base_daily,stock_code=000001 open=10.5,high=10.8,low=10.2,close=10.6,volume=1000,amount=5000,adj_factor=1.0,prev_close=10.4 1707004800000000000
    line = f"base_daily,stock_code={stock_code} " \
           f"open={row.get('open', 0) or 0}," \
           f"high={row.get('high', 0) or 0}," \
           f"low={row.get('low', 0) or 0}," \
           f"close={row.get('close', 0) or 0}," \
           f"volume={row.get('vol', 0) or 0}," \
           f"amount={row.get('amount', 0) or 0}," \
           f"adj_factor={row.get('adj_factor', 1) or 1}," \
           f"prev_close={row.get('pre_close', 0) or 0} " \
           f"{ts_nanos}"
    
    ilp_lines.append(line)

# 发送 ILP 数据到 QuestDB
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 9009))
    
    # 批量发送
    batch_size = 1000
    sent_count = 0
    
    for i in range(0, len(ilp_lines), batch_size):
        batch = ilp_lines[i:i+batch_size]
        data = '\n'.join(batch) + '\n'
        sock.sendall(data.encode('utf-8'))
        sent_count += len(batch)
        print(f"   已发送 {sent_count}/{len(ilp_lines)} 条")
    
    sock.close()
    print(f"   ✅ 成功发送 {sent_count} 条 ILP 记录")
    
except Exception as e:
    print(f"   ❌ ILP 发送失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 5. 等待数据写入并验证
print(f"\n[5] 等待 3 秒后验证...")
import time
time.sleep(3)

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
    else:
        print(f"   ❌ 数据未找到")

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
