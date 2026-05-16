"""
检查因子数据和股票数据的日期格式
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
from datetime import datetime


def check_date_formats():
    """检查日期格式"""
    print("=" * 70)
    print("检查日期格式")
    print("=" * 70)
    
    # 检查股票数据
    stock_path = Path('data/parquet_data/stock_daily.parquet')
    stock_df = pl.scan_parquet(str(stock_path))
    stock_schema = stock_df.collect_schema()
    
    print(f"\n股票数据 trade_date 类型: {stock_schema['trade_date']}")
    
    stock_sample = stock_df.filter(pl.col('trade_date') == datetime(2026, 2, 27).date()).head(1).collect()
    print(f"股票数据 2026-02-27 样本: {stock_sample['trade_date'].to_list() if not stock_sample.is_empty() else '无数据'}")
    
    # 检查因子数据
    factor_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    factor_df = pl.scan_parquet(str(factor_path))
    factor_schema = factor_df.collect_schema()
    
    print(f"\n因子数据 trade_date 类型: {factor_schema['trade_date']}")
    
    factor_sample = factor_df.filter(pl.col('trade_date') == datetime(2026, 2, 27).date()).head(1).collect()
    print(f"因子数据 2026-02-27 样本: {factor_sample['trade_date'].to_list() if not factor_sample.is_empty() else '无数据'}")
    
    # 检查因子数据中 2026-02-27 的 MA20 数据
    factor_2026 = factor_df.filter(pl.col('trade_date') == datetime(2026, 2, 27).date()).collect()
    print(f"\n因子数据 2026-02-27 数据量: {len(factor_2026)} 行")
    
    if not factor_2026.is_empty():
        ma20_null = factor_2026['ma20'].null_count()
        print(f"因子数据 MA20 null: {ma20_null}/{len(factor_2026)}")


if __name__ == '__main__':
    check_date_formats()
