#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断 LanceDB 数据"""
import lancedb
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'lancedb')
print(f'DB Path: {db_path}')
print(f'Exists: {os.path.exists(db_path)}')

db = lancedb.connect(db_path)
result = db.list_tables()
tables = result.tables if hasattr(result, 'tables') else list(result)
print(f'Tables: {tables}')

# Check stock_info
if 'stock_info' in tables:
    tbl = db.open_table('stock_info')
    df = tbl.to_pandas()
    print(f'\nstock_info: {len(df)} rows')
    print(f'Columns: {list(df.columns)}')
    if not df.empty:
        print(df.head(3))
else:
    print('\nstock_info table NOT FOUND')

# Check factors
if 'factors' in tables:
    tbl = db.open_table('factors')
    df = tbl.to_pandas()
    print(f'\nfactors: {len(df)} rows')
    cols = list(df.columns)
    print(f'Columns ({len(cols)}): {cols[:30]}')
    target_cols = ['corr_60d', 'beta_60d', 'alpha_60d', 'stock_code', 'trade_date']
    for col in target_cols:
        if col in cols:
            print(f'  {col}: EXISTS')
        else:
            print(f'  {col}: NOT FOUND')
    # Check stock_code format
    if 'stock_code' in df.columns:
        sample = df['stock_code'].head(5).tolist()
        print(f'  stock_code sample: {sample}')
    # Check trade_date format
    if 'trade_date' in df.columns:
        sample = df['trade_date'].head(3).tolist()
        print(f'  trade_date sample: {sample}')
        print(f'  trade_date dtype: {df["trade_date"].dtype}')
else:
    print('\nfactors table NOT FOUND')

# Check daily_ohlcv
if 'daily_ohlcv' in tables:
    tbl = db.open_table('daily_ohlcv')
    df = tbl.to_pandas()
    print(f'\ndaily_ohlcv: {len(df)} rows')
    print(f'Columns: {list(df.columns)[:15]}')
    if 'stock_code' in df.columns:
        sample = df['stock_code'].head(3).tolist()
        print(f'stock_code sample: {sample}')
