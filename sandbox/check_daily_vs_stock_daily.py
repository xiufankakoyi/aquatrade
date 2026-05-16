from pathlib import Path
from arcticdb import Arctic
import pandas as pd

base_path = Path('data/arctic_db')

# 检查 stock_daily 库
print("=" * 50)
print("stock_daily 库 (老库 - 源)")
print("=" * 50)
stock_daily_path = base_path / 'stock_daily'
if stock_daily_path.exists():
    arctic = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')
    lib = arctic['stock_daily']
    symbols = lib.list_symbols()
    print(f"股票数量: {len(symbols)}")
    
    # 抽样检查数据范围
    sample_symbols = symbols[:3]
    for s in sample_symbols:
        item = lib.read(s)
        df = item.data
        print(f"  {s}: {df.index.min()} ~ {df.index.max()}, 共 {len(df)} 条")

# 检查 daily 库
print("\n" + "=" * 50)
print("daily 库 (新库 - 目标)")
print("=" * 50)
daily_path = base_path / 'daily'
if daily_path.exists():
    arctic = Arctic(f'lmdb://{daily_path}?map_size=10GB')
    try:
        lib = arctic['daily']
        symbols = lib.list_symbols()
        print(f"股票数量: {len(symbols)}")
        
        if symbols:
            sample_symbols = symbols[:3]
            for s in sample_symbols:
                item = lib.read(s)
                df = item.data
                print(f"  {s}: {df.index.min()} ~ {df.index.max()}, 共 {len(df)} 条")
        else:
            print("  (空库)")
    except Exception as e:
        print(f"  错误: {e}")
else:
    print("  库不存在，需要创建")
