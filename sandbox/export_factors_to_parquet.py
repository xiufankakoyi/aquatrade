"""
从 ArcticDB 重新导出因子数据到 Parquet
"""
import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import polars as pl
import pandas as pd
from loguru import logger
from data_svc.storage.arcticdb_manager import get_arctic_instance_for_library
from datetime import datetime
import pyarrow as pa


def export_factors_to_parquet():
    """从 ArcticDB 导出因子数据到 Parquet"""
    print("=" * 70)
    print("从 ArcticDB 导出因子数据到 Parquet")
    print("=" * 70)
    
    arctic = get_arctic_instance_for_library('factor')
    lib = arctic['factor']
    
    symbols = lib.list_symbols()
    print(f"Symbol 数量: {len(symbols)}")
    
    all_data = []
    processed = 0
    
    for symbol in symbols:
        try:
            data = lib.read(symbol)
            df = data.data
            
            if hasattr(df, 'to_pandas'):
                df = df.to_pandas()
            
            # 重置索引
            df = df.reset_index()
            
            # 重命名索引列为 trade_date（无论原列名是什么）
            index_name = df.index.name if hasattr(df.index, 'name') else None
            if index_name:
                df = df.rename(columns={index_name: 'trade_date'})
            elif 'index' in df.columns:
                df = df.rename(columns={'index': 'trade_date'})
            elif 'date' in df.columns:
                df = df.rename(columns={'date': 'trade_date'})
            
            # 从 symbol 中提取股票代码
            stock_code = symbol.replace('momentum_', '')
            df['stock_code'] = stock_code
            
            all_data.append(df)
            
            processed += 1
            if processed % 500 == 0:
                print(f"  处理进度: {processed}/{len(symbols)}")
                
        except Exception as e:
            logger.warning(f"处理 {symbol} 失败: {e}")
    
    print(f"\n合并数据...")
    combined = pd.concat(all_data, ignore_index=True)
    
    print(f"总行数: {len(combined)}")
    print(f"列: {list(combined.columns)}")
    
    # 检查 MA 列
    ma_cols = ['ma5', 'ma10', 'ma20', 'ma60']
    print("\nMA 列统计:")
    for col in ma_cols:
        if col in combined.columns:
            null_count = combined[col].isna().sum()
            print(f"  {col}: null={null_count}/{len(combined)}")
    
    # 转换为 Polars 并保存
    print("\n转换为 Polars...")
    pl_df = pl.from_pandas(combined)
    
    # 处理日期类型
    if 'trade_date' in pl_df.columns:
        if pl_df['trade_date'].dtype == pl.Datetime:
            pl_df = pl_df.with_columns(
                pl.col('trade_date').dt.date().alias('trade_date')
            )
    
    # 保存
    output_path = Path('data/parquet_data/factors_momentum_hot.parquet')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n保存到: {output_path}")
    pl_df.write_parquet(str(output_path))
    
    print("✅ 导出完成!")
    
    # 验证
    print("\n验证导出结果...")
    verify_df = pl.scan_parquet(str(output_path)).collect()
    print(f"  行数: {len(verify_df)}")
    
    for col in ma_cols:
        if col in verify_df.columns:
            null_count = verify_df[col].null_count()
            print(f"  {col}: null={null_count}/{len(verify_df)}")


if __name__ == '__main__':
    export_factors_to_parquet()
