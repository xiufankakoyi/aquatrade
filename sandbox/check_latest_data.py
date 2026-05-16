"""
检查最新日期的数据
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl


def check_latest_data():
    """检查最新日期的数据"""
    parquet_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    
    lazy_df = pl.scan_parquet(str(parquet_path))
    
    # 获取最新日期
    latest = lazy_df.select(pl.col('trade_date').max()).collect()
    latest_date = latest['trade_date'][0]
    
    print(f"最新日期: {latest_date}")
    
    # 获取最新日期的数据
    df = lazy_df.filter(pl.col('trade_date') == latest_date).collect()
    
    print(f"数据量: {len(df)} 行")
    
    if not df.is_empty():
        print(f"\n列: {list(df.columns)}")
        
        # 检查 MA 列
        ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
        for col in ma_cols:
            if col in df.columns:
                null_count = df[col].null_count()
                print(f"  {col}: null={null_count}/{len(df)}")
        
        # 显示样本
        print(f"\n样本数据:")
        sample = df.head(5)
        for row in sample.iter_rows(named=True):
            ma5 = row.get('ma5')
            ma10 = row.get('ma10')
            ma20 = row.get('ma20')
            print(f"  {row.get('stock_code')}: ma5={ma5:.2f if ma5 else 'N/A'}, ma10={ma10:.2f if ma10 else 'N/A'}, ma20={ma20:.2f if ma20 else 'N/A'}")


if __name__ == '__main__':
    check_latest_data()
