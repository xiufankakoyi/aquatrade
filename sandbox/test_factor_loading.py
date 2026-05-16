"""
测试因子加载
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['LOG_LEVEL'] = 'DEBUG'

import polars as pl
from pathlib import Path
from core.strategies.utils.factor_calculator import FactorCalculator, PARQUET_DIR, ALL_DB_FACTORS

print("=" * 80)
print("因子加载测试")
print("=" * 80)

print(f"\nPARQUET_DIR: {PARQUET_DIR}")
print(f"PARQUET_DIR exists: {PARQUET_DIR.exists()}")

hot_path = PARQUET_DIR / "factors_momentum_hot.parquet"
archive_path = PARQUET_DIR / "factors_momentum_archive.parquet"

print(f"\nhot_path: {hot_path}")
print(f"hot_path exists: {hot_path.exists()}")

print(f"\narchive_path: {archive_path}")
print(f"archive_path exists: {archive_path.exists()}")

print(f"\nALL_DB_FACTORS: {ALL_DB_FACTORS}")

if hot_path.exists():
    print("\n加载 hot 数据...")
    hot_df = pl.read_parquet(hot_path)
    print(f"hot_df shape: {hot_df.shape}")
    print(f"hot_df columns: {hot_df.columns}")
    
    if 'ma5' in hot_df.columns:
        sample = hot_df.filter(pl.col('trade_date') == '2024-01-02').select(['stock_code', 'trade_date', 'ma5', 'ma10']).head(5)
        print(f"\n2024-01-02 样本数据:")
        print(sample)

calc = FactorCalculator()

print(f"\nFactorCalculator._loaded: {calc._loaded}")
print(f"FactorCalculator._hot_df: {calc._hot_df is not None}")
print(f"FactorCalculator._archive_df: {calc._archive_df is not None}")

trading_dates = ['2024-01-02', '2024-01-03', '2024-01-04']
stock_codes = ['000001', '000002', '600000']

print(f"\n加载因子: ma5, ma10")
factors = calc.load_factors(
    factor_names=['ma5', 'ma10'],
    trading_dates=trading_dates,
    stock_codes=stock_codes,
)

print(f"\n加载结果:")
for name, matrix in factors.items():
    print(f"  {name}: shape={matrix.shape}")

print(f"\nFactorCalculator._loaded: {calc._loaded}")
print(f"FactorCalculator._hot_df: {calc._hot_df is not None}")
if calc._hot_df is not None:
    print(f"FactorCalculator._hot_df shape: {calc._hot_df.shape}")
