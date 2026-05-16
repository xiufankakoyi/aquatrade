#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 stock_daily 库中的数据结构"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic["stock_daily"]
data = lib.read("stock_daily")
df = data.data
print(f"数据类型: {type(df)}")

# 转换为 pandas DataFrame
df = df.to_pandas()
print(f"转换后类型: {type(df)}")
print(f"数据形状: {df.shape}")
print(f"列名: {df.columns.tolist()[:10]}")
print(f"索引: {df.index.names}")
print(f"前几行:")
print(df.head())
