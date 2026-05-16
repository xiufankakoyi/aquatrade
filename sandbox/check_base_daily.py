"""
检查原始数据源
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_base_daily():
    """检查 base_daily_hot.parquet"""
    parquet_path = Path('data/parquet_data/base_daily_hot.parquet')
    
    if not parquet_path.exists():
        print(f"文件不存在: {parquet_path}")
        return
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    schema = lazy_df.collect_schema()
    
    print("=" * 70)
    print("检查 base_daily_hot.parquet")
    print("=" * 70)
    
    print(f"\n列: {list(schema.keys())}")
    
    # 检查日期范围
    date_range = lazy_df.select([
        pl.col('trade_date').min().alias('min_date'),
        pl.col('trade_date').max().alias('max_date')
    ]).collect()
    
    print(f"\n日期范围:")
    print(f"  最小: {date_range['min_date'][0]}")
    print(f"  最大: {date_range['max_date'][0]}")
    
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
            else:
                print(f"  {col}: 列不存在")


if __name__ == '__main__':
    check_base_daily()
