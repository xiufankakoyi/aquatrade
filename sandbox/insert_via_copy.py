"""
使用 COPY 方式批量插入数据（适用于 BYPASS WAL 表）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests
import pandas as pd
import io
from datetime import datetime
from config.config import Config

print("=" * 70)
print("使用 COPY 方式插入数据")
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

# 3. 准备数据为 CSV 格式
print(f"\n[4] 准备 CSV 数据...")
df_daily['stock_code'] = df_daily['ts_code'].str.split('.', expand=True)[0]
df_daily['timestamp'] = pd.to_datetime(target_date, format='%Y%m%d')

# 重命名列以匹配表结构
df_daily['volume'] = df_daily['vol']
df_daily['prev_close'] = df_daily['pre_close']
df_daily['adj_factor'] = 1.0  # Tushare daily 接口不返回复权因子，使用默认值

# 选择需要的列
df_insert = df_daily[['timestamp', 'stock_code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'adj_factor', 'prev_close']]

# 处理缺失值
df_insert = df_insert.fillna({
    'open': 0, 'high': 0, 'low': 0, 'close': 0,
    'volume': 0, 'amount': 0, 'adj_factor': 1, 'prev_close': 0
})

# 保存为 CSV
csv_buffer = io.StringIO()
df_insert.to_csv(csv_buffer, index=False, header=False)
csv_data = csv_buffer.getvalue()

print(f"   ✅ CSV 数据准备完成，大小: {len(csv_data)} 字节")

# 5. 使用 COPY 命令导入
print(f"\n[5] 使用 COPY 导入...")

# QuestDB 的 COPY 命令
# 格式: COPY table_name FROM 'file.csv' WITH HEADER false;
# 但由于是内存数据，我们使用 INSERT 批量插入

# 批量 INSERT
batch_size = 100
success_count = 0

for i in range(0, len(df_insert), batch_size):
    batch = df_insert.iloc[i:i+batch_size]
    
    # 构建批量 INSERT
    values_list = []
    for _, row in batch.iterrows():
        ts = row['timestamp'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        values = f"('{row['stock_code']}', {row['open']}, {row['high']}, {row['low']}, {row['close']}, {row['volume']}, {row['amount']}, {row['adj_factor']}, {row['prev_close']}, '{ts}')"
        values_list.append(values)
    
    insert_sql = f"INSERT INTO base_daily (stock_code, open, high, low, close, volume, amount, adj_factor, prev_close, timestamp) VALUES {', '.join(values_list)}"
    
    try:
        resp = requests.get(
            'http://localhost:9000/exec',
            params={'query': insert_sql},
            timeout=30
        )
        if resp.status_code == 200:
            success_count += len(batch)
            if (i + batch_size) % 1000 == 0 or i + batch_size >= len(df_insert):
                print(f"   已插入 {min(i+batch_size, len(df_insert))}/{len(df_insert)} 条")
        else:
            print(f"   插入失败: {resp.text[:100]}")
            break
    except Exception as e:
        print(f"   错误: {e}")
        break

print(f"   ✅ 成功插入 {success_count} 条记录")

# 6. 验证
print(f"\n[6] 验证...")
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

# 7. 检查后端 API
print(f"\n[7] 检查后端 API...")
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
