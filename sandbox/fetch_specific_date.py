"""
获取特定日期的数据并手动添加到 Parquet
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
import polars as pl
from datetime import datetime
from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)

def fetch_and_add_date(target_date: str):
    """
    获取指定日期的数据并添加到 Parquet
    
    Args:
        target_date: 目标日期 (YYYY-MM-DD 或 YYYYMMDD)
    """
    print(f"=" * 80)
    print(f"获取并添加 {target_date} 的数据")
    print(f"=" * 80)
    
    # 标准化日期格式
    if '-' in target_date:
        target_date = target_date.replace('-', '')
    
    # 1. 检查数据是否已存在
    parquet_path = os.path.join(Config.PARQUET_DIR, "stock_daily.parquet")
    if os.path.exists(parquet_path):
        try:
            df_existing = pl.scan_parquet(parquet_path)
            existing_dates = df_existing.select("trade_date").unique().collect().to_series().to_list()
            
            # 转换日期格式进行比较
            existing_dates_str = []
            for d in existing_dates:
                if isinstance(d, str):
                    existing_dates_str.append(d.replace('-', ''))
                else:
                    existing_dates_str.append(pd.to_datetime(d).strftime('%Y%m%d'))
            
            if target_date in existing_dates_str:
                print(f"\n⚠️  {target_date} 的数据已存在，跳过")
                return True
        except Exception as e:
            logger.warning(f"检查现有数据失败: {e}")
    
    # 2. 从 Tushare 获取数据
    print(f"\n[1] 从 Tushare 获取 {target_date} 的数据...")
    try:
        import tushare as ts
        ts.set_token(Config.TUSHARE_TOKEN)
        pro = ts.pro_api()
        
        # 获取日线数据
        df_daily = pro.daily(trade_date=target_date)
        if df_daily is None or df_daily.empty:
            print(f"   ❌ {target_date} 没有数据")
            return False
        
        print(f"   ✅ 获取到 {len(df_daily)} 条日线数据")
        
        # 获取基本面数据
        df_basic = pro.daily_basic(trade_date=target_date, fields=[
            'ts_code', 'trade_date', 'turnover_rate', 'turnover_rate_f',
            'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
            'dv_ratio', 'dv_ttm', 'total_mv', 'circ_mv',
            'total_share', 'float_share', 'free_share'
        ])
        
        # 获取复权因子
        df_adj = pro.adj_factor(trade_date=target_date)
        
        # 合并数据
        if df_basic is not None and not df_basic.empty:
            df_daily = pd.merge(df_daily, df_basic, on=['ts_code', 'trade_date'], how='left')
            print(f"   ✅ 合并基本面数据")
        
        if df_adj is not None and not df_adj.empty:
            df_daily = pd.merge(df_daily, df_adj[['ts_code', 'trade_date', 'adj_factor']], 
                              on=['ts_code', 'trade_date'], how='left')
            print(f"   ✅ 合并复权因子")
        
    except Exception as e:
        print(f"   ❌ 获取数据失败: {e}")
        return False
    
    # 3. 处理数据格式
    print(f"\n[2] 处理数据格式...")
    try:
        df_daily['stock_code'] = df_daily['ts_code'].str.split('.', expand=True)[0]
        df_daily['trade_date'] = pd.to_datetime(df_daily['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
        
        # 重命名列
        df_daily.rename(columns={
            'vol': 'volume',
            'pct_chg': 'change_pct',
            'change': 'change_amount',
            'pre_close': 'prev_close',
            'circ_mv': 'float_mv',
            'turnover_rate_f': 'turnover_free',
            'dv_ratio': 'dividend_yield',
            'dv_ttm': 'dividend_yield_ttm',
            'total_share': 'total_shares',
            'float_share': 'float_shares',
            'free_share': 'free_float_shares'
        }, inplace=True)
        
        print(f"   ✅ 数据处理完成，共 {len(df_daily)} 条记录")
    except Exception as e:
        print(f"   ❌ 数据处理失败: {e}")
        return False
    
    # 4. 写入 Parquet
    print(f"\n[3] 写入 Parquet...")
    try:
        df_new_pl = pl.from_pandas(df_daily)
        
        if os.path.exists(parquet_path):
            # 读取现有数据
            df_existing = pl.scan_parquet(parquet_path)
            existing_schema = df_existing.collect_schema()
            existing_cols = set(existing_schema.names())
            new_cols = set(df_new_pl.columns)
            
            # 确保列一致
            missing_cols = existing_cols - new_cols
            for col in missing_cols:
                df_new_pl = df_new_pl.with_columns(pl.lit(None).alias(col))
            
            extra_cols = new_cols - existing_cols
            if extra_cols:
                logger.warning(f"新数据包含额外列 (将被忽略): {extra_cols}")
            
            df_new_pl = df_new_pl.select(existing_schema.names())
            
            # 合并数据
            df_combined = pl.concat([df_existing.collect(), df_new_pl])
            df_combined.write_parquet(parquet_path)
        else:
            df_new_pl.write_parquet(parquet_path)
        
        print(f"   ✅ 数据已写入 Parquet")
        return True
        
    except Exception as e:
        print(f"   ❌ 写入 Parquet 失败: {e}")
        return False

if __name__ == "__main__":
    # 更新 2026-02-11 的数据
    success = fetch_and_add_date("2026-02-11")
    
    if success:
        print(f"\n✅ 2026-02-11 数据更新成功!")
    else:
        print(f"\n❌ 2026-02-11 数据更新失败!")
