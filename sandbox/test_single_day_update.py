"""
测试单日数据更新脚本 (含技术指标计算)
=====================================
测试 ParquetUpdater 的增量更新功能，包含本地计算技术指标
"""
import os
import sys
import time
import datetime
import pandas as pd
import polars as pl
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


def calculate_technical_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """
    计算技术指标
    
    包括: MA, BIAS, 涨跌停价
    """
    print(f"\n[计算技术指标]...")
    
    df = df.sort(['stock_code', 'trade_date'])
    
    close = df['close'].to_numpy()
    high = df['high'].to_numpy()
    low = df['low'].to_numpy()
    prev_close = df['prev_close'].to_numpy()
    
    ma5 = np.full(len(df), np.nan)
    ma10 = np.full(len(df), np.nan)
    ma20 = np.full(len(df), np.nan)
    ma3_avg_price = np.full(len(df), np.nan)
    ma5_avg_price = np.full(len(df), np.nan)
    ma10_avg_price = np.full(len(df), np.nan)
    volume_ma5 = np.full(len(df), np.nan)
    limit_up = np.full(len(df), np.nan)
    limit_down = np.full(len(df), np.nan)
    
    stock_codes = df['stock_code'].to_numpy()
    volumes = df['volume'].to_numpy()
    amounts = df['amount'].to_numpy()
    
    unique_codes = np.unique(stock_codes)
    
    for code in unique_codes:
        mask = stock_codes == code
        indices = np.where(mask)[0]
        
        if len(indices) < 5:
            continue
        
        code_close = close[indices]
        code_high = high[indices]
        code_low = low[indices]
        code_prev_close = prev_close[indices]
        code_volume = volumes[indices]
        code_amount = amounts[indices]
        
        for i, idx in enumerate(indices):
            if i >= 4:
                ma5[idx] = np.mean(code_close[i-4:i+1])
                volume_ma5[idx] = np.mean(code_volume[i-4:i+1])
                
                avg_price = code_amount[i] / code_volume[i] if code_volume[i] > 0 else code_close[i]
                if i >= 2:
                    ma3_avg_price[idx] = np.mean([
                        code_amount[i-2] / code_volume[i-2] if code_volume[i-2] > 0 else code_close[i-2],
                        code_amount[i-1] / code_volume[i-1] if code_volume[i-1] > 0 else code_close[i-1],
                        avg_price
                    ])
                ma5_avg_price[idx] = avg_price
            
            if i >= 9:
                ma10[idx] = np.mean(code_close[i-9:i+1])
                ma10_avg_price[idx] = code_amount[i] / code_volume[i] if code_volume[i] > 0 else code_close[i]
            
            if i >= 19:
                ma20[idx] = np.mean(code_close[i-19:i+1])
        
        for i, idx in enumerate(indices):
            pc = code_prev_close[i] if i > 0 else (code_close[i] * 0.9 if code_close[i] > 0 else 10)
            if pc > 0:
                limit_up[idx] = round(pc * 1.1, 2)
                limit_down[idx] = round(pc * 0.9, 2)
    
    df = df.with_columns([
        pl.Series('ma5', ma5),
        pl.Series('ma10', ma10),
        pl.Series('ma20', ma20),
        pl.Series('ma3_avg_price', ma3_avg_price),
        pl.Series('ma5_avg_price', ma5_avg_price),
        pl.Series('ma10_avg_price', ma10_avg_price),
        pl.Series('volume_ma5', volume_ma5),
        pl.Series('limit_up', limit_up),
        pl.Series('limit_down', limit_down),
    ])
    
    print(f"    MA5: {df['ma5'].null_count()} null / {len(df)}")
    print(f"    MA10: {df['ma10'].null_count()} null / {len(df)}")
    print(f"    MA20: {df['ma20'].null_count()} null / {len(df)}")
    
    return df


def test_single_day_update():
    """测试单日数据更新"""
    print("=" * 60)
    print("测试单日数据更新 (含技术指标计算)")
    print("=" * 60)
    
    if not TUSHARE_AVAILABLE:
        print("错误: tushare 未安装，请运行: pip install tushare")
        return False
    
    token = Config.TUSHARE_TOKEN
    if not token:
        print("错误: TUSHARE_TOKEN 未配置，请在 .env 文件中设置")
        return False
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    parquet_dir = Config.PARQUET_DIR
    parquet_path = os.path.join(parquet_dir, "stock_daily.parquet")
    
    print(f"\n[1] Parquet 路径: {parquet_path}")
    print(f"    文件存在: {os.path.exists(parquet_path)}")
    
    existing_schema = None
    existing_cols = None
    if os.path.exists(parquet_path):
        df_existing = pl.scan_parquet(parquet_path)
        existing_schema = df_existing.collect_schema()
        existing_cols = set(existing_schema.names())
        print(f"    现有列数: {len(existing_cols)}")
        
        last_date = df_existing.select(pl.col("trade_date").max()).collect().item()
        print(f"    最后日期: {last_date}")
    else:
        print("    错误: Parquet 文件不存在")
        return False
    
    today = datetime.date.today()
    test_date = today.strftime('%Y%m%d')
    
    print(f"\n[2] 尝试获取 {test_date} 的数据...")
    
    max_retries = 5
    df_daily = None
    
    for attempt in range(max_retries):
        try:
            print(f"    尝试 {attempt + 1}/{max_retries}...")
            df_daily = pro.daily(trade_date=test_date)
            if df_daily is not None and not df_daily.empty:
                print(f"    成功! 获取到 {len(df_daily)} 条记录")
                break
            else:
                print(f"    该日期无数据 (可能是非交易日)")
                test_date = (today - datetime.timedelta(days=1)).strftime('%Y%m%d')
                print(f"    尝试前一天: {test_date}")
                df_daily = pro.daily(trade_date=test_date)
                if df_daily is not None and not df_daily.empty:
                    print(f"    成功! 获取到 {len(df_daily)} 条记录")
                    break
        except Exception as e:
            print(f"    失败: {e}")
            time.sleep(2)
    
    if df_daily is None or df_daily.empty:
        print("错误: 无法获取数据")
        return False
    
    print(f"\n[3] 获取辅助数据...")
    
    df_basic = None
    df_adj = None
    
    for attempt in range(max_retries):
        try:
            print(f"    获取 daily_basic (完整字段)...")
            df_basic = pro.daily_basic(trade_date=test_date, fields=[
                'ts_code', 'trade_date', 'turnover_rate', 'turnover_rate_f',
                'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm',
                'dv_ratio', 'dv_ttm', 'total_mv', 'circ_mv',
                'total_share', 'float_share', 'free_share'
            ])
            print(f"    获取 adj_factor...")
            df_adj = pro.adj_factor(trade_date=test_date)
            break
        except Exception as e:
            print(f"    失败: {e}, 重试...")
            time.sleep(2)
    
    if df_basic is not None and not df_basic.empty:
        df_daily = pd.merge(df_daily, df_basic, on=['ts_code', 'trade_date'], how='left')
        print(f"    合并 daily_basic: {len(df_daily)} 条")
    
    if df_adj is not None and not df_adj.empty:
        df_daily = pd.merge(df_daily, df_adj[['ts_code', 'trade_date', 'adj_factor']], on=['ts_code', 'trade_date'], how='left')
        print(f"    合并 adj_factor: {len(df_daily)} 条")
    
    print(f"\n[4] 数据预处理...")
    
    df_daily['stock_code'] = df_daily['ts_code'].str.split('.', expand=True)[0]
    df_daily['trade_date'] = pd.to_datetime(df_daily['trade_date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    
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
    
    df_new_pl = pl.from_pandas(df_daily)
    print(f"    新数据列数: {len(df_new_pl.columns)}")
    
    print(f"\n[5] 列对齐 (合并前)...")
    
    new_cols = set(df_new_pl.columns)
    missing_cols = existing_cols - new_cols
    
    if missing_cols:
        print(f"    新数据缺失列 ({len(missing_cols)}): {sorted(missing_cols)}")
        for col in missing_cols:
            df_new_pl = df_new_pl.with_columns(pl.lit(None).alias(col))
    
    extra_cols = new_cols - existing_cols
    if extra_cols:
        print(f"    额外列 (将被忽略): {extra_cols}")
    
    df_new_pl = df_new_pl.select(existing_schema.names())
    print(f"    对齐后列数: {len(df_new_pl.columns)}")
    
    print(f"\n[6] 读取历史数据用于计算技术指标...")
    
    df_existing_full = pl.scan_parquet(parquet_path).collect()
    print(f"    历史数据: {len(df_existing_full)} 条")
    
    last_60_days = df_existing_full.filter(
        pl.col('trade_date') >= (pd.to_datetime(test_date) - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    )
    print(f"    最近60天数据: {len(last_60_days)} 条")
    
    df_combined = pl.concat([last_60_days, df_new_pl])
    print(f"    合并后用于计算: {len(df_combined)} 条")
    
    df_with_indicators = calculate_technical_indicators(df_combined)
    
    df_new_with_indicators = df_with_indicators.filter(
        pl.col('trade_date') == pd.to_datetime(test_date).strftime('%Y-%m-%d')
    )
    print(f"    新数据 (含指标): {len(df_new_with_indicators)} 条")
    
    print(f"\n[7] 最终列检查...")
    
    new_cols = set(df_new_with_indicators.columns)
    missing_cols = existing_cols - new_cols
    
    if missing_cols:
        print(f"    缺失列 ({len(missing_cols)}): {sorted(missing_cols)}")
        for col in missing_cols:
            df_new_with_indicators = df_new_with_indicators.with_columns(pl.lit(None).alias(col))
    else:
        print(f"    无缺失列!")
    
    extra_cols = new_cols - existing_cols
    if extra_cols:
        print(f"    额外列 (将被忽略): {extra_cols}")
    
    df_new_with_indicators = df_new_with_indicators.select(existing_schema.names())
    print(f"    对齐后列数: {len(df_new_with_indicators.columns)}")
    
    print(f"\n[8] 合并数据...")
    
    df_existing_collected = pl.scan_parquet(parquet_path).collect()
    print(f"    现有数据: {len(df_existing_collected)} 条")
    
    df_final = pl.concat([df_existing_collected, df_new_with_indicators])
    print(f"    合并后: {len(df_final)} 条")
    
    print(f"\n[9] 写入 Parquet...")
    
    backup_path = parquet_path + ".backup"
    if os.path.exists(parquet_path):
        import shutil
        shutil.copy(parquet_path, backup_path)
        print(f"    备份已创建: {backup_path}")
    
    df_final.write_parquet(parquet_path)
    print(f"    写入成功!")
    
    print(f"\n[10] 验证...")
    
    df_verify = pl.scan_parquet(parquet_path)
    new_last_date = df_verify.select(pl.col("trade_date").max()).collect().item()
    new_count = df_verify.select(pl.len()).collect().item()
    
    print(f"    新的最后日期: {new_last_date}")
    print(f"    新的总行数: {new_count}")
    
    expected_date = pd.to_datetime(test_date).strftime('%Y-%m-%d')
    if new_last_date == expected_date:
        print(f"\n" + "=" * 60)
        print("测试成功! 技术指标已计算并写入")
        print("=" * 60)
        return True
    else:
        print(f"\n警告: 日期不匹配，期望 {expected_date}, 实际 {new_last_date}")
        return False


if __name__ == "__main__":
    success = test_single_day_update()
    sys.exit(0 if success else 1)
