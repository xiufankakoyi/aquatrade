import pandas as pd
from pathlib import Path

# 检查 ArcticDB 数据
base_path = Path('data/arctic_db')

# 检查 stock_daily 库
stock_daily_path = base_path / 'stock_daily'

if stock_daily_path.exists():
    print(f'stock_daily 路径存在: {stock_daily_path}')

    try:
        from arcticdb import Arctic
        arctic = Arctic(f'lmdb://{stock_daily_path}?map_size=10GB')

        # 列出所有 symbol
        lib = arctic['stock_daily']
        symbols = lib.list_symbols()
        print(f'stock_daily 共有 {len(symbols)} 个股票数据')

        if symbols:
            # 检查前几个股票的数据范围
            for symbol in symbols[:5]:
                try:
                    item = lib.read(symbol)
                    df = item.data
                    if df is not None and not df.empty:
                        min_date = df.index.min()
                        max_date = df.index.max()
                        df_2024 = df[df.index.year == 2024]
                        print(f'{symbol}: {min_date} ~ {max_date}, 共 {len(df)} 条, 2024年有 {len(df_2024)} 条')
                except Exception as e:
                    print(f'读取 {symbol} 失败: {e}')
    except Exception as e:
        print(f'ArcticDB 错误: {e}')
else:
    print(f'stock_daily 路径不存在')
