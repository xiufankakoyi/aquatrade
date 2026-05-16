"""
检查因子数据中 2026-02-27 的 MA 数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from datetime import datetime


def check_factor_data():
    """检查因子数据"""
    factor_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(factor_path))
    schema = lazy_df.collect_schema()
    
    print("=" * 70)
    print("因子数据检查")
    print("=" * 70)
    
    print(f"\ntrade_date 类型: {schema['trade_date']}")
    
    # 过滤 2026-02-27
    target_date = datetime(2026, 2, 27).date()
    df = lazy_df.filter(pl.col('trade_date') == target_date).collect()
    
    print(f"\n2026-02-27 数据量: {len(df)} 行")
    
    # 检查 MA 列
    ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
    for col in ma_cols:
        if col in df.columns:
            null_count = df[col].null_count()
            print(f"  {col}: null={null_count}/{len(df)}")
    
    # 显示有 MA20 数据的样本
    has_ma20 = df.filter(pl.col('ma20').is_not_null())
    print(f"\n有 MA20 数据的股票数: {len(has_ma20)}")
    
    if not has_ma20.is_empty():
        sample = has_ma20.head(3)
        for row in sample.iter_rows(named=True):
            print(f"  {row.get('stock_code')}: ma5={row.get('ma5'):.2f}, ma10={row.get('ma10'):.2f}, ma20={row.get('ma20'):.2f}")


if __name__ == '__main__':
    check_factor_data()
