#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 market_data 库的结构
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()

if "market_data" in arctic.list_libraries():
    lib = arctic["market_data"]
    symbols = list(lib.list_symbols())
    
    print(f'market_data 库中有 {len(symbols)} 个 symbols')
    
    # 检查特定股票
    for code in ['603256.SH', '600941.SH', '000066.SZ', '513050.SH', '009690.SZ']:
        if code in symbols:
            print(f'\n  {code}: 存在')
            # 读取数据
            data = lib.read(code)
            df = data.data
            if df is not None and not df.empty:
                print(f'    列名: {list(df.columns)}')
                print(f'    最新日期: {df.index[-1]}')
                print(f'    最新数据: {df.iloc[-1].to_dict()}')
        else:
            print(f'\n  {code}: 不存在')
else:
    print('market_data 库不存在')
