"""
创建测试数据并导入 ArcticDB
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from sandbox.arctic_store import ArcticDataStore


def generate_stock_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """生成模拟股票数据"""
    dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日
    n = len(dates)
    
    # 生成随机价格数据
    np.random.seed(hash(symbol) % 2**32)
    returns = np.random.randn(n) * 0.02  # 2% 日波动
    prices = 10 * np.exp(np.cumsum(returns))  # 从 10 元开始
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(n) * 0.01),
        'high': prices * (1 + np.abs(np.random.randn(n)) * 0.02),
        'low': prices * (1 - np.abs(np.random.randn(n)) * 0.02),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n),
        'amount': np.random.randint(10000000, 100000000, n),
        'adj_factor': np.ones(n),
    }, index=dates)
    
    # 确保 high >= open >= low, high >= close >= low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def main():
    print("创建测试数据并导入 ArcticDB")
    print("=" * 60)
    
    # 创建 ArcticDB 存储
    store = ArcticDataStore()
    
    # 生成 10 只测试股票的数据
    test_symbols = [
        '000001.SZ', '000002.SZ', '000333.SZ', '000858.SZ', '002415.SZ',
        '600000.SH', '600036.SH', '600519.SH', '601318.SH', '601888.SH'
    ]
    
    start_date = '2024-01-01'
    end_date = '2024-12-31'
    
    print(f"\n生成 {len(test_symbols)} 只股票的测试数据...")
    print(f"时间范围: {start_date} ~ {end_date}")
    
    for symbol in test_symbols:
        # 生成数据
        df = generate_stock_data(symbol, start_date, end_date)
        
        # 写入 ArcticDB
        store.write_daily_data(symbol, df)
        print(f"  ✓ {symbol}: {len(df)} 条记录")
    
    # 打印统计
    print("\n")
    store.print_stats()
    
    # 测试读取
    print("\n测试读取数据...")
    df = store.read('000001.SZ', start_date='2024-06-01', end_date='2024-06-30', as_polars=True)
    print(f"  000001.SZ 2024年6月数据: {len(df)} 行")
    if not df.is_empty():
        # Polars DataFrame 的 columns 已经是 list
        columns = df.columns
        print(f"  列: {columns}")
        print(f"  前5行:")
        print(df.head().to_pandas().to_string())
    
    store.close()
    print("\n测试数据创建完成!")


if __name__ == "__main__":
    main()
