import sys
sys.path.insert(0, 'C:/Users/Liu/Desktop/projects/aquatrade')
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library

# 检查因子库
arctic = get_arctic_instance_for_library('factor')
lib = arctic['factor']
symbols = lib.list_symbols()
print(f'因子库 symbol 数量: {len(symbols)}')

# 检查日期范围
if symbols:
    data = lib.read(symbols[0])
    df = data.data
    print(f'因子日期范围: {df.index.min()} ~ {df.index.max()}')

# 检查涨跌停状态库
arctic2 = get_arctic_instance_for_library('limit_status')
lib2 = arctic2['limit_status']
symbols2 = lib2.list_symbols()
print(f'\n涨跌停状态库 symbol 数量: {len(symbols2)}')

if symbols2:
    data2 = lib2.read('000001.SZ')
    df2 = data2.data
    print(f'涨跌停状态日期范围: {df2.index.min()} ~ {df2.index.max()}')
