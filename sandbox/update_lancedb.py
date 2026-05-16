"""
使用Tushare更新LanceDB数据到最新日期
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tushare as ts
import polars as pl
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger
import lancedb

from config.config import Config


def get_trade_dates(pro, start_date: str, end_date: str) -> list:
    """获取交易日列表"""
    cal_df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
    return cal_df[cal_df['is_open'] == 1]['cal_date'].tolist()


def update_lancedb(end_date: str = None):
    """
    更新LanceDB数据
    
    Args:
        end_date: 目标结束日期 (YYYYMMDD)，默认今天
    """
    token = Config.TUSHARE_TOKEN
    if not token:
        raise ValueError("TUSHARE_TOKEN 未配置")
    
    pro = ts.pro_api(token)
    
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    db_path = Path(__file__).parent.parent / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    # 获取当前数据最新日期
    if "daily_ohlcv" in db.table_names():
        table = db.open_table("daily_ohlcv")
        df = pl.from_arrow(table.to_arrow())
        df = df.with_columns(pl.col('trade_date').cast(pl.Datetime).dt.strftime('%Y%m%d'))
        max_date = df['trade_date'].max()
        start_date = (datetime.strptime(max_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
        logger.info(f"当前数据最新日期: {max_date}")
    else:
        start_date = '20200101'
        logger.info(f"数据库为空，从 {start_date} 开始")
    
    if start_date > end_date:
        logger.info("数据已是最新，无需更新")
        return
    
    # 获取交易日
    trade_dates = get_trade_dates(pro, start_date, end_date)
    if not trade_dates:
        logger.info("没有需要更新的交易日")
        return
    
    logger.info(f"需要更新 {len(trade_dates)} 个交易日: {trade_dates[0]} ~ {trade_dates[-1]}")
    
    # 获取数据
    all_data = []
    for i, trade_date in enumerate(trade_dates):
        logger.info(f"获取 {trade_date} 数据 ({i+1}/{len(trade_dates)})")
        
        try:
            df_daily = pro.daily(trade_date=trade_date)
            if df_daily is None or df_daily.empty:
                continue
            
            df_basic = pro.daily_basic(trade_date=trade_date)
            if df_basic is not None and not df_basic.empty:
                df = pd.merge(df_daily, df_basic, on='ts_code', how='left', suffixes=('', '_basic'))
            else:
                df = df_daily
            
            df['stock_code'] = df['ts_code'].str.split('.', expand=True)[0]
            all_data.append(df)
            
        except Exception as e:
            logger.error(f"获取 {trade_date} 失败: {e}")
    
    if not all_data:
        logger.warning("没有获取到新数据")
        return
    
    # 合并数据
    combined = pd.concat(all_data, ignore_index=True)
    
    # 转换为Polars
    df_pl = pl.from_pandas(combined)
    
    # 规范化列名和格式
    col_mapping = {
        'trade_date': 'trade_date',
        'stock_code': 'stock_code',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'vol': 'volume',
        'amount': 'amount',
        'pct_chg': 'change_pct',
        'turnover_rate': 'turnover_rate',
        'total_mv': 'total_mv',
        'circ_mv': 'float_mv',
    }
    
    # 重命名列
    rename_map = {k: v for k, v in col_mapping.items() if k in df_pl.columns}
    df_pl = df_pl.rename(rename_map)
    
    # 转换日期格式
    df_pl = df_pl.with_columns(
        pl.col('trade_date').str.to_date('%Y%m%d')
    )
    
    # 选择需要的列
    keep_cols = ['stock_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
    optional_cols = ['change_pct', 'turnover_rate', 'total_mv', 'float_mv']
    for col in optional_cols:
        if col in df_pl.columns:
            keep_cols.append(col)
    
    df_pl = df_pl.select([c for c in keep_cols if c in df_pl.columns])
    
    # 写入LanceDB
    if "daily_ohlcv" in db.table_names():
        table = db.open_table("daily_ohlcv")
        # 删除已存在的日期数据
        for td in trade_dates:
            try:
                table.delete(f'trade_date = "{td}"')
            except:
                pass
        # 追加新数据
        table.add(df_pl.to_arrow())
        logger.info(f"追加 {len(df_pl)} 行数据")
    else:
        table = db.create_table("daily_ohlcv", df_pl.to_arrow())
        table.create_scalar_index("trade_date", replace=True)
        logger.info(f"创建表并写入 {len(df_pl)} 行数据")
    
    # 更新指数数据
    logger.info("更新指数数据...")
    update_index_data(pro, db, start_date, end_date)
    
    logger.info("数据更新完成!")


def update_index_data(pro, db, start_date: str, end_date: str):
    """更新指数数据"""
    index_codes = {
        '000001.SH': '上证指数',
        '000016.SH': '上证50',
        '000300.SH': '沪深300',
        '000905.SH': '中证500',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
    }
    
    all_data = []
    for code, name in index_codes.items():
        logger.info(f"获取 {name} ({code})")
        try:
            df = pro.index_daily(ts_code=code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df['symbol'] = code
                df['name'] = name
                all_data.append(df)
        except Exception as e:
            logger.error(f"获取 {code} 失败: {e}")
    
    if not all_data:
        return
    
    combined = pd.concat(all_data, ignore_index=True)
    df_pl = pl.from_pandas(combined)
    
    # 规范化列名
    rename_map = {}
    for k, v in {'trade_date': 'trade_date', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'vol': 'volume', 'amount': 'amount'}.items():
        if k in df_pl.columns and v not in df_pl.columns:
            rename_map[k] = v
    if rename_map:
        df_pl = df_pl.rename(rename_map)
    
    df_pl = df_pl.with_columns(
        pl.col('trade_date').str.to_date('%Y%m%d')
    )
    
    keep_cols = ['symbol', 'trade_date', 'close', 'open', 'high', 'low', 'volume', 'amount', 'name']
    df_pl = df_pl.select([c for c in keep_cols if c in df_pl.columns])
    
    if "index_daily" in db.table_names():
        table = db.open_table("index_daily")
        for code in index_codes.keys():
            try:
                table.delete(f'symbol = "{code}"')
            except:
                pass
        table.add(df_pl.to_arrow())
        logger.info(f"追加指数数据 {len(df_pl)} 行")
    else:
        table = db.create_table("index_daily", df_pl.to_arrow())
        logger.info(f"创建指数表并写入 {len(df_pl)} 行")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYYMMDD)')
    args = parser.parse_args()
    
    update_lancedb(args.end_date)
