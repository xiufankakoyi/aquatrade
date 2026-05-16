"""
检查 Parquet 因子数据中的 MA 列
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_parquet_ma():
    """检查 Parquet 中的 MA 数据"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    if not parquet_path.exists():
        print(f"❌ 文件不存在: {parquet_path}")
        return
    
    print("=" * 70)
    print("检查 Parquet 因子数据")
    print("=" * 70)
    
    # 读取 schema
    lazy_df = pl.scan_parquet(str(parquet_path))
    schema = lazy_df.collect_schema()
    
    print(f"\n列: {list(schema.keys())}")
    
    # 读取最新日期的数据
    df = lazy_df.sort('trade_date', descending=True).head(100).collect()
    
    print(f"\n最新日期: {df['trade_date'][0]}")
    print(f"行数: {len(df)}")
    
    # 检查 MA 列
    ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
    
    print("\nMA 列统计:")
    for col in ma_cols:
        if col in df.columns:
            null_count = df[col].null_count()
            non_null = df[col].drop_nulls()
            if len(non_null) > 0:
                print(f"  {col}: null={null_count}/{len(df)}, 范围=[{non_null.min():.2f}, {non_null.max():.2f}]")
            else:
                print(f"  {col}: 全部为 null")
        else:
            print(f"  {col}: 列不存在")
    
    # 显示样本数据
    print("\n样本数据 (前5行):")
    sample = df.head(5)
    for row in sample.iter_rows(named=True):
        print(f"  {row.get('stock_code')}: ma5={row.get('ma5'):.2f}, ma10={row.get('ma10'):.2f}, ma20={row.get('ma20'):.2f}")


if __name__ == '__main__':
    check_parquet_ma()
