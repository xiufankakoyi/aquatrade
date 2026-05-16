"""
检查 Parquet 数据来源
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_parquet_source():
    """检查 Parquet 数据来源"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 检查数据分布
    print("=" * 70)
    print("检查 Parquet 数据分布")
    print("=" * 70)
    
    # 按年份统计
    yearly = lazy_df.group_by(
        pl.col('trade_date').dt.year().alias('year')
    ).len().sort('year').collect()
    
    print("\n按年份统计:")
    for row in yearly.iter_rows(named=True):
        print(f"  {row['year']}: {row['len']} 行")
    
    # 检查 2026 年数据
    df_2026 = lazy_df.filter(pl.col('trade_date').dt.year() == 2026).collect()
    
    print(f"\n2026 年数据: {len(df_2026)} 行")
    
    if not df_2026.is_empty():
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        print("\n2026 年 MA 列统计:")
        for col in ma_cols:
            if col in df_2026.columns:
                null_count = df_2026[col].null_count()
                print(f"  {col}: null={null_count}/{len(df_2026)}")
        
        # 检查 stock_code 分布
        codes = df_2026.select('stock_code').unique()
        print(f"\n2026 年股票数量: {len(codes)}")


if __name__ == '__main__':
    check_parquet_source()
