"""
调试因子矩阵构建过程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
import pandas as pd
import polars as pl
import numpy as np

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)

start_date = '2025-06-03'
end_date = '2025-06-10'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

if preloaded_data and 'stock_daily' in preloaded_data:
    df = preloaded_data['stock_daily']
    print(f"原始数据:")
    print(f"  行数: {len(df)}")
    print(f"  列: {df.columns}")
    print(f"\n前5行:")
    print(df.head())
    
    # 检查日期和股票代码
    trading_dates = df['trade_date'].unique().sort().to_list()
    print(f"\n日期数: {len(trading_dates)}")
    print(f"日期: {trading_dates[:5]}...")
    
    stock_codes = df['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()
    print(f"\n股票数: {len(stock_codes)}")
    print(f"前10个股票代码: {stock_codes[:10]}")
    
    # 模拟 FactorMatrixBuilder 的构建过程
    from core.backtest.factor_matrix import FactorMatrixBuilder
    
    builder = FactorMatrixBuilder()
    factor_names = builder.factor_names
    print(f"\n因子名: {factor_names}")
    
    available_factors = [c for c in factor_names if c in df.columns]
    print(f"可用因子: {available_factors}")
    
    # 构建索引映射
    trading_dates_str = [str(d) for d in trading_dates]
    date_to_idx = {date: i for i, date in enumerate(trading_dates_str)}
    
    stock_codes_str = [str(c).zfill(6) for c in stock_codes]
    code_to_idx = {code: i for i, code in enumerate(stock_codes_str)}
    
    print(f"\ndate_to_idx (前5个): {list(date_to_idx.items())[:5]}")
    print(f"code_to_idx (前5个): {list(code_to_idx.items())[:5]}")
    
    # 创建带索引的 DataFrame
    df_with_idx = df.select(['trade_date', 'stock_code'] + available_factors).with_columns([
        pl.col('trade_date').cast(pl.Utf8).replace_strict(date_to_idx, default=None).alias('date_idx'),
        pl.col('stock_code').cast(pl.Utf8).str.strip_chars().replace_strict(code_to_idx, default=None).alias('code_idx')
    ])
    
    print(f"\ndf_with_idx 行数: {len(df_with_idx)}")
    print(f"date_idx null 数量: {df_with_idx['date_idx'].null_count()}")
    print(f"code_idx null 数量: {df_with_idx['code_idx'].null_count()}")
    
    # 过滤
    df_filtered = df_with_idx.filter(
        pl.col('date_idx').is_not_null() & pl.col('code_idx').is_not_null()
    )
    
    print(f"\n过滤后行数: {len(df_filtered)}")
    
    if len(df_filtered) > 0:
        print(f"\n过滤后前5行:")
        print(df_filtered.head())
        
        # 检查 open 列的数据
        open_vals = df_filtered['open'].to_numpy()
        print(f"\nopen 列统计:")
        print(f"  非null数量: {np.sum(~np.isnan(open_vals))}")
        print(f"  null数量: {np.sum(np.isnan(open_vals))}")
        print(f"  最小值: {np.nanmin(open_vals)}")
        print(f"  最大值: {np.nanmax(open_vals)}")
else:
    print("预加载数据为空或没有 stock_daily")
