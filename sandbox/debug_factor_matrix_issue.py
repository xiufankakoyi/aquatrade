"""
调试因子矩阵构建 - 检查 code_to_idx 映射问题
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.backtest.factor_matrix import stock_codes_to_int_vectorized_polars
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
    
    # 检查原始股票代码
    stock_codes = df['stock_code'].cast(pl.Utf8).str.strip_chars().unique().sort().to_list()
    print(f"原始股票代码 (前10个): {stock_codes[:10]}")
    
    # 转换为6位字符串
    stock_codes_str = [str(c).zfill(6) for c in stock_codes]
    print(f"转换后股票代码 (前10个): {stock_codes_str[:10]}")
    
    # 转换为整数
    codes_int = stock_codes_to_int_vectorized_polars(pl.Series(stock_codes_str))
    print(f"整数代码 (前10个): {codes_int[:10].tolist()}")
    
    # 构建 code_to_idx
    code_to_idx = {str(c): i for i, c in enumerate(stock_codes_str)}
    print(f"\ncode_to_idx (前5个): {list(code_to_idx.items())[:5]}")
    
    # 问题：FactorMatrixBuilder 使用的是 codes_int 作为键
    code_to_idx_int = {str(c): i for i, c in enumerate(codes_int)}
    print(f"code_to_idx_int (前5个): {list(code_to_idx_int.items())[:5]}")
    
    # 检查 replace_strict 使用的映射
    replace_map = {str(c): i for i, c in enumerate(stock_codes_str)}
    print(f"\nreplace_strict 映射 (前5个): {list(replace_map.items())[:5]}")
    
    # 检查原始 df 中的 stock_code
    print(f"\n原始 df 中的 stock_code (前10个): {df['stock_code'].head(10).to_list()}")
    
    # 检查转换后的 stock_code
    df_codes = df['stock_code'].cast(pl.Utf8).str.strip_chars().to_list()
    print(f"转换后的 stock_code (前10个): {df_codes[:10]}")
    
    # 检查哪些代码在映射中找不到
    missing_codes = [c for c in df_codes if c not in replace_map]
    print(f"\n找不到的代码数量: {len(missing_codes)}")
    print(f"找不到的代码 (前10个): {missing_codes[:10]}")
