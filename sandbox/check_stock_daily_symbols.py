from pathlib import Path
from arcticdb import Arctic

# 检查 stock_daily 库的 symbol 格式
stock_daily_path = Path('data/arctic_db/stock_daily')
arctic = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')

lib = arctic['stock_daily']
symbols = lib.list_symbols()
print(f'stock_daily 共有 {len(symbols)} 个 symbol')
print(f'前10个symbol: {symbols[:10]}')

# 读取一个样本
if symbols:
    item = lib.read(symbols[0])
    df = item.data
    print(f'\n{symbols[0]} 数据列: {list(df.columns)}')
    print(f'前3行:\n{df.head(3)}')
