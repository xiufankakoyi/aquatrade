"""
完整的缺失日期填补脚本
流程：
1. 检查缺失日期
2. 从 Tushare 获取数据
3. 插入到 QuestDB
4. 验证插入结果
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
from questdb.ingress import Sender

print("=" * 70)
print("缺失日期填补脚本")
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
    print("\n✅ 没有缺失日期，数据完整！")
    exit(0)

# 2. 选择第一个缺失日期
target_date = missing[0]
target_date_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
print(f"\n[2] 选择目标日期: {target_date_fmt}")

# 3. 从 Tushare 获取数据
print(f"\n[3] 从 Tushare 获取 {target_date_fmt} 的数据...")
try:
    import tushare as ts
    ts.set_token(Config.TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    df_daily = pro.daily(trade_date=target_date)
    if df_daily is None or df_daily.empty:
        print(f"   ❌ {target_date_fmt} 没有数据（可能不是交易日）")
        exit(1)
    
    print(f"   ✅ 获取到 {len(df_daily)} 条数据")
    print(f"   样本数据:\n{df_daily.head(3)}")
    
except Exception as e:
    print(f"   ❌ 获取数据失败: {e}")
    exit(1)

# 4. 准备数据
print(f"\n[4] 准备数据...")
df_daily['stock_code'] = df_daily['ts_code'].str.split('.', expand=True)[0]

# 准备插入的数据
records = []
for _, row in df_daily.iterrows():
    # 使用本地时间（QuestDB 会自动处理时区）
    ts = pd.to_datetime(target_date, format='%Y%m%d')
    
    record = {
        'stock_code': row['stock_code'],
        'open': float(row.get('open', 0) or 0),
        'high': float(row.get('high', 0) or 0),
        'low': float(row.get('low', 0) or 0),
        'close': float(row.get('close', 0) or 0),
        'volume': float(row.get('vol', 0) or 0),
        'amount': float(row.get('amount', 0) or 0),
        'adj_factor': float(row.get('adj_factor', 1) or 1),
        'prev_close': float(row.get('pre_close', 0) or 0),
        'timestamp': ts
    }
    records.append(record)

print(f"   ✅ 准备了 {len(records)} 条记录")

# 5. 插入到 QuestDB
print(f"\n[5] 插入到 QuestDB...")
try:
    inserted = 0
    with Sender('tcp', 'localhost', 9009) as sender:
        for record in records:
            sender.row(
                'base_daily',
                symbols={'stock_code': record['stock_code']},
                columns={
                    'open': record['open'],
                    'high': record['high'],
                    'low': record['low'],
                    'close': record['close'],
                    'volume': record['volume'],
                    'amount': record['amount'],
                    'adj_factor': record['adj_factor'],
                    'prev_close': record['prev_close'],
                },
                at=record['timestamp']
            )
            inserted += 1
        
        sender.flush()
    
    print(f"   ✅ 成功插入 {inserted} 条记录")
    
except Exception as e:
    print(f"   ❌ 插入失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 6. 直接验证 QuestDB
print(f"\n[6] 直接验证 QuestDB...")
resp = requests.get(
    'http://localhost:9000/exec',
    params={'query': f"SELECT COUNT(*) FROM base_daily WHERE date_trunc('day', timestamp) = '{target_date_fmt}'"},
    timeout=5
)
data = resp.json()
if 'dataset' in data and data['dataset']:
    count = data['dataset'][0][0]
    print(f"   QuestDB 中 {target_date_fmt} 的数据条数: {count}")
    if count > 0:
        print(f"   ✅ 数据确实已插入 QuestDB")
    else:
        print(f"   ❌ QuestDB 中没有数据")

# 7. 验证后端 API
print(f"\n[7] 验证后端 API...")
resp = requests.get(
    "http://localhost:5000/api/db/missing_dates",
    params={"start_date": target_date_fmt, "end_date": target_date_fmt},
    timeout=5
)
data = resp.json()
missing_after = data.get("missing_dates", [])

if target_date not in missing_after:
    print(f"   ✅ {target_date_fmt} 不再缺失！")
else:
    print(f"   ❌ {target_date_fmt} 仍然显示为缺失")
    print(f"   后端返回: {data}")

# 8. 检查最后日期
print(f"\n[8] 检查最后更新日期...")
resp = requests.get("http://localhost:5000/api/db/last_date", timeout=5)
data = resp.json()
print(f"   最后日期: {data.get('last_date')}")

print("\n" + "=" * 70)
print("脚本执行完成")
print("=" * 70)
