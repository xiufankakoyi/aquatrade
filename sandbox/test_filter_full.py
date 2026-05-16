#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整测试筛选器流程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
from server.routes.screener_routes import (
    get_stock_daily_df, get_latest_trade_date, 
    apply_filter_conditions_pl, clean_nan_values
)

print("=" * 70)
print("完整测试筛选器流程")
print("=" * 70)

# 获取数据
df = get_stock_daily_df()
print(f"\n1. 获取数据")
print(f"   类型: {type(df)}")
print(f"   行数: {len(df)}")

# 获取日期
date = '2026-02-13'
print(f"\n2. 过滤日期: {date}")

try:
    date_obj = pd.to_datetime(date).date()
    print(f"   日期对象: {date_obj} (类型: {type(date_obj)})")
    date_data = df.filter(pl.col('trade_date') == date_obj)
    print(f"   过滤后行数: {len(date_data)}")
    print(f"   是否为空: {date_data.is_empty()}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 添加 stock_code
print(f"\n3. 添加 stock_code")
if 'stock_code' not in date_data.columns and 'ts_code' in date_data.columns:
    try:
        date_data = date_data.with_columns(
            pl.col('ts_code').str.split('.').list.get(0).alias('stock_code')
        )
        print(f"   成功添加 stock_code 列")
        print(f"   列: {date_data.columns}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()

# 应用筛选条件
print(f"\n4. 应用筛选条件")
try:
    df_filtered = apply_filter_conditions_pl(date_data, [], 'AND')
    print(f"   筛选后行数: {len(df_filtered)}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 获取总数
print(f"\n5. 获取总数")
try:
    total = df_filtered.select(pl.len()).to_series().to_list()[0]
    print(f"   总数: {total}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 排序
print(f"\n6. 排序")
try:
    df_filtered = df_filtered.sort('total_mv', descending=True)
    print(f"   排序后行数: {len(df_filtered)}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 分页
print(f"\n7. 分页")
try:
    df_filtered = df_filtered.slice(0, 20)
    print(f"   分页后行数: {len(df_filtered)}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 转换为 pandas
print(f"\n8. 转换为 pandas")
try:
    result_pdf = df_filtered.to_pandas()
    print(f"   类型: {type(result_pdf)}")
    print(f"   行数: {len(result_pdf)}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 选择字段
print(f"\n9. 选择字段")
try:
    default_fields = [
        'stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'change_pct',
        'volume', 'amount', 'turnover_rate', 'total_mv', 'float_mv',
        'pe', 'pb', 'ma5', 'ma10', 'ma20'
    ]
    select_fields = [f for f in default_fields if f in result_pdf.columns]
    print(f"   选择的字段: {select_fields}")
    result_pdf = result_pdf[select_fields]
    print(f"   选择后行数: {len(result_pdf)}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

# 转换为字典
print(f"\n10. 转换为字典")
try:
    records = result_pdf.to_dict('records')
    print(f"   记录数: {len(records)}")
    if records:
        print(f"   第一条记录: {records[0]}")
except Exception as e:
    print(f"   错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
