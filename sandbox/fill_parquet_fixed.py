"""
填补 Parquet 缺失日期 - 修复版
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests
import pandas as pd
import polars as pl
from datetime import datetime
from config.config import Config

print("=" * 70)
print("填补 Parquet 缺失日期")
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

# 2. 选择第一个缺失日期
target_date = missing[0]
target_date_fmt = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
print(f"\n[2] 目标日期: {target_date_fmt}")

# 3. 从 Tushare 获取数据
print(f"\n[3] 从 Tushare 获取数据...")
import tushare as ts
ts.set_token(Config.TUSHARE_TOKEN)
pro = ts.pro_api()

df_daily = pro.daily(trade_date=target_date)
if df_daily is None or df_daily.empty:
    print(f"   ❌ 没有数据（可能不是交易日）")
    exit(1)

print(f"   ✅ 获取到 {len(df_daily)} 条数据")

# 4. 读取现有 Parquet
print(f"\n[4] 读取现有 Parquet...")
parquet_path = str(Path(Config.PARQUET_DIR) / "stock_daily.parquet")

# 使用 Polars 读取
df_existing = pl.scan_parquet(parquet_path)
existing_count = df_existing.select(pl.count()).collect().item()
print(f"   现有记录数: {existing_count}")

# 获取现有列
existing_cols = df_existing.collect_schema().names()
print(f"   列数: {len(existing_cols)}")

# 5. 准备新数据
print(f"\n[5] 准备新数据...")

# 转换 pandas 到 polars
df_new = pl.from_pandas(df_daily)

# 添加 trade_date 列
df_new = df_new.with_columns([
    pl.lit(target_date_fmt).alias('trade_date')
])

# 提取 stock_code
df_new = df_new.with_columns([
    pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
])

# 确保所有现有列都存在
for col in existing_cols:
    if col not in df_new.columns:
        df_new = df_new.with_columns([pl.lit(None).alias(col)])

# 只选择需要的列
df_new = df_new.select(existing_cols)

print(f"   新数据列: {df_new.columns}")
print(f"   新数据行数: {len(df_new)}")

# 6. 合并数据
print(f"\n[6] 合并数据...")
df_combined = pl.concat([df_existing.collect(), df_new])
print(f"   合并后行数: {len(df_combined)}")

# 7. 写入 Parquet
print(f"\n[7] 写入 Parquet...")
df_combined.write_parquet(parquet_path)
print(f"   ✅ 数据已写入 Parquet")

# 8. 验证
print(f"\n[8] 验证...")
df_verify = pl.scan_parquet(parquet_path)
new_count = df_verify.filter(pl.col('trade_date') == target_date_fmt).select(pl.count()).collect().item()
print(f"   {target_date_fmt} 数据条数: {new_count}")

if new_count > 0:
    print(f"   ✅ 数据插入成功！")

# 9. 检查后端 API
print(f"\n[9] 检查后端 API...")
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
