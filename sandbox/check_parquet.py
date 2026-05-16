#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'C:\Users\Liu\Desktop\projects\aquatrade')

from pathlib import Path
from config.config import Config
import polars as pl

def check_parquet():
    """检查 Parquet 源文件"""
    parquet_path = Path(Config.PARQUET_DIR) / "stock_daily.parquet"
    
    print(f"Parquet 路径: {parquet_path}")
    print(f"文件存在: {parquet_path.exists()}")
    
    if parquet_path.exists():
        # 读取元数据
        df = pl.scan_parquet(parquet_path)
        
        print(f"\n列: {df.columns}")
        
        # 获取行数
        total_rows = df.select(pl.len()).collect().item()
        print(f"总行数: {total_rows}")
        
        # 获取日期范围
        if 'trade_date' in df.columns:
            dates = df.select('trade_date').unique().collect().to_series().to_list()
            print(f"日期数量: {len(dates)}")
            print(f"日期范围: {sorted(dates)[:3]} ... {sorted(dates)[-3:]}")
        
        # 获取股票数量
        if 'stock_code' in df.columns:
            stocks = df.select('stock_code').unique().collect().to_series().to_list()
            print(f"股票数量: {len(stocks)}")

if __name__ == '__main__':
    check_parquet()
