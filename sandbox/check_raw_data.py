"""检查原始数据源中的股票代码"""
import pandas as pd
import os

# 检查 CSV 数据源
csv_paths = [
    'data/marketdata/沪深300.csv',
    'data/marketdata/中证500.csv',
    'data/marketdata/全市场.csv',
]

for path in csv_paths:
    if os.path.exists(path):
        print(f'\n=== {path} ===')
        df = pd.read_csv(path, nrows=100)
        print(f'列名: {df.columns.tolist()}')
        if '股票代码' in df.columns:
            print(f'股票代码示例: {df["股票代码"].head(20).tolist()}')
            
            # 统计各板块
            codes = df['股票代码'].unique()
            sz_count = sum(1 for c in codes if str(c).startswith('0'))
            cyb_count = sum(1 for c in codes if str(c).startswith('3'))
            sh_count = sum(1 for c in codes if str(c).startswith('6'))
            kcb_count = sum(1 for c in codes if str(c).startswith('688'))
            
            print(f'沪市主板(6开头): {sh_count}')
            print(f'科创板(688): {kcb_count}')
            print(f'深市主板(0开头): {sz_count}')
            print(f'创业板(3开头): {cyb_count}')
    else:
        print(f'文件不存在: {path}')

# 检查是否有其他数据源
print('\n=== data/marketdata 目录 ===')
if os.path.exists('data/marketdata'):
    files = os.listdir('data/marketdata')
    for f in files:
        print(f'  {f}')
