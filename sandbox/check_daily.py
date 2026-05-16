#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 daily 库中的数据"""
import sys
sys.path.insert(0, 'c:/Users/Liu/Desktop/projects/aquatrade')

from data_svc.storage.arcticdb_manager import get_arctic_instance

arctic = get_arctic_instance()
lib = arctic["daily"]
print("daily 库中的符号:")
for symbol in lib.list_symbols():
    print(f"  - {symbol}")
