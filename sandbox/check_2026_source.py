"""
检查 factors_momentum_hot.parquet 的 2026 年数据来源
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_2026_source():
    """检查 2026 年数据来源"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 获取 2026 年数据
    df_2026 = lazy_df.filter(pl.col('trade_date').dt.year() == 2026).collect()
    
    print("=" * 70)
    print("检查 2026 年数据")
    print("=" * 70)
    
    print(f"\n数据量: {len(df_2026)} 行")
    
    # 检查列
    print(f"\n列: {list(df_2026.columns)}")
    
    # 检查 stock_code 分布
    codes = df_2026.select('stock_code').unique()
    print(f"\n股票数量: {len(codes)}")
    
    # 检查日期分布
    dates = df_2026.select('trade_date').unique().sort('trade_date')
    print(f"\n日期数量: {len(dates)}")
    print(f"日期范围: {dates['trade_date'][0]} ~ {dates['trade_date'][-1]}")
    
    # 检查一个股票的数据
    sample_code = codes['stock_code'][0]
    sample_df = df_2026.filter(pl.col('stock_code') == sample_code).sort('trade_date')
    
    print(f"\n样本股票 {sample_code} 数据:")
    print(f"  行数: {len(sample_df)}")
    
    # 检查 MA 列
    ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
    print("\n  MA 列统计:")
    for col in ma_cols:
        if col in sample_df.columns:
            null_count = sample_df[col].null_count()
            print(f"    {col}: null={null_count}/{len(sample_df)}")


if __name__ == '__main__':
    check_2026_source()
