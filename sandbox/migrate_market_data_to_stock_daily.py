#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将 market_data 库的历史数据迁移到 stock_daily 库

【重要说明】
===========
这个脚本用于解决 stock_daily 库数据不完整的问题。

背景：
------
- market_data 库: 按股票代码分 symbol 存储，有完整历史数据 (2010-2026)
- stock_daily 库: 单 symbol 存储，用于股票筛选器和回测

问题：
------
- unified_updater.py 默认是增量更新，只更新最近的数据到 stock_daily
- 导致 stock_daily 可能只有几天的数据，而不是完整的历史数据
- 股票筛选器和回测需要完整的历史数据才能正常工作

解决方案：
----------
运行此脚本，将 market_data 中的所有历史数据合并到 stock_daily 库中。

使用方法：
----------
    python sandbox/migrate_market_data_to_stock_daily.py

注意事项：
----------
1. 此操作会覆盖 stock_daily 库的现有数据
2. 迁移完成后，stock_daily 库将包含 2010-01-04 ~ 2026-02-13 的完整数据
3. 数据量约 700 万行，需要几分钟时间
4. 迁移完成后需要重新运行因子预计算：
   python sandbox/precompute_all_factors.py

相关文档：
----------
- sandbox/DATABASE_DEVELOPMENT_NOTES.md: 数据库开发常见问题
- data_svc/storage/factor_precompute_service.py: 因子预计算服务
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl
import pandas as pd
from loguru import logger
from datetime import datetime

from data_svc.storage.arcticdb_manager import get_arctic_instance
from data_svc.unified_data_manager import UnifiedDataManager


def migrate_market_data_to_stock_daily():
    """迁移数据"""
    print("=" * 70)
    print("迁移 market_data 到 stock_daily")
    print("=" * 70)
    
    arctic = get_arctic_instance()
    manager = UnifiedDataManager()
    
    # 检查库是否存在
    if "market_data" not in arctic.list_libraries():
        print("错误: market_data 库不存在")
        return False
    
    market_lib = arctic["market_data"]
    symbols = market_lib.list_symbols()
    print(f"\nmarket_data 库有 {len(symbols)} 只股票")
    
    # 读取所有数据并合并
    print("\n正在读取所有股票数据...")
    all_data = []
    total_rows = 0
    
    for i, symbol in enumerate(symbols):
        if (i + 1) % 500 == 0 or i == len(symbols) - 1:
            print(f"  进度: {i+1}/{len(symbols)} ({(i+1)/len(symbols)*100:.1f}%)")
        
        try:
            data = market_lib.read(symbol)
            
            # 【关键步骤 1】转换为 pandas，保留索引
            # market_data 库的 trade_date 是索引，不是列
            if hasattr(data.data, 'to_pandas'):
                df = data.data.to_pandas()
            else:
                df = data.data
            
            # 【关键步骤 2】重置索引，将 trade_date 转为列
            # 这是必须的，因为 stock_daily 库需要 trade_date 作为列
            df = df.reset_index()
            
            # 【关键步骤 3】确保 trade_date 是 datetime 类型
            # 统一日期格式，避免后续处理出错
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
            
            all_data.append(df)
            total_rows += len(df)
            
        except Exception as e:
            logger.warning(f"读取 {symbol} 失败: {e}")
    
    print(f"\n总共读取 {len(all_data)} 只股票，{total_rows:,} 行数据")
    
    # 【关键步骤 4】合并所有数据
    # 使用 ignore_index=True 重新生成索引
    print("\n正在合并数据...")
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"合并后: {len(combined_df):,} 行")
    
    # 检查列
    print(f"\n列名: {list(combined_df.columns)}")
    
    # 【关键步骤 5】转换为 Polars DataFrame
    # UnifiedDataManager.write() 需要 Polars DataFrame 作为输入
    # 它会自动转换为 Arrow Table 后写入 ArcticDB
    print("\n转换为 Polars DataFrame...")
    pl_df = pl.from_pandas(combined_df)
    
    # 检查日期范围
    if 'trade_date' in pl_df.columns:
        print(f"\n日期范围: {pl_df['trade_date'].min()} ~ {pl_df['trade_date'].max()}")
        print(f"唯一日期数: {pl_df['trade_date'].n_unique()}")
    
    # 【关键步骤 6】写入 stock_daily 库
    # 使用 UnifiedDataManager 写入，它会处理格式转换
    print("\n正在写入 stock_daily 库...")
    result = manager.write('stock_daily', 'stock_daily', pl_df)
    
    if result.success:
        print("\n✓ 数据迁移完成!")
        print(f"  总记录数: {result.rows:,}")
        print(f"  版本: {result.version}")
        print(f"  耗时: {result.elapsed_ms:.2f}ms")
        return True
    else:
        print(f"\n✗ 写入失败: {result.error}")
        return False


if __name__ == '__main__':
    migrate_market_data_to_stock_daily()
