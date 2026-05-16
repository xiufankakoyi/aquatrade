"""
检查 Parquet 文件中的股票数据
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd

def check_parquet():
    parquet_file = "data/parquet_data/stock_daily.parquet"

    print("=" * 60)
    print("检查 Parquet 股票数据")
    print("=" * 60)

    if not os.path.exists(parquet_file):
        print(f"文件不存在: {parquet_file}")
        return

    try:
        df = pd.read_parquet(parquet_file)
        print(f"\n数据形状: {df.shape}")
        print(f"列: {list(df.columns)}")
        print(f"\n日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        print(f"股票数量: {df['stock_code'].nunique()}")

        # 检查2024年数据
        df_2024 = df[df['trade_date'].str.startswith('2024')]
        print(f"\n2024年数据记录数: {len(df_2024)}")

        # 检查2025年数据
        df_2025 = df[df['trade_date'].str.startswith('2025')]
        print(f"2025年数据记录数: {len(df_2025)}")

        # 检查2026年数据
        df_2026 = df[df['trade_date'].str.startswith('2026')]
        print(f"2026年数据记录数: {len(df_2026)}")

        # 最新日期
        print(f"\n最新数据日期: {df['trade_date'].max()}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_parquet()
