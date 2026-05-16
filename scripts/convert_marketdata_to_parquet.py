"""
将 marketdata CSV 文件转换为 Parquet 格式
"""
import pandas as pd
from pathlib import Path

# 定义文件映射
FILE_MAPPING = {
    '沪深300.csv': 'hs300_daily.parquet',
    '中证500.csv': 'zz500_daily.parquet',
    '上证指数数据.csv': 'sh_index_daily.parquet',
    '深证成指数据.csv': 'sz_index_daily.parquet',
    '上证50.csv': 'sz50_daily.parquet',
    '创业板指数数据.csv': 'cyb_index_daily.parquet',
}

# 列名映射（中文 -> 英文）
COLUMN_MAPPING = {
    '股票代码': 'symbol',
    '交易日期': 'date',
    '开盘价': 'open',
    '最高价': 'high',
    '最低价': 'low',
    '收盘价': 'close',
    '前收盘价': 'prev_close',
    '涨跌额': 'change_amount',
    '涨跌幅(%)': 'change_pct',
    '成交量(手)': 'volume',
    '成交额(万元)': 'amount',
    '当日总市值(十万元)': 'total_mv',
    '当日流通市值(十万元)': 'float_mv',
    '当日总股本(万股)': 'total_shares',
    '当日流通股本(万股)': 'float_shares',
    '当日自由流通股本(万股)': 'free_float_shares',
    '换手率(%)': 'turnover_rate',
    '换手率(自由流通股)': 'turnover_free',
    '市盈率': 'pe',
    '市盈率(TTM)': 'pe_ttm',
    '市净率': 'pb',
}


def convert_csv_to_parquet(csv_file: Path, output_file: Path):
    """转换单个 CSV 文件为 Parquet"""
    print(f"Converting {csv_file.name}...")
    
    # 读取 CSV
    df = pd.read_csv(csv_file, encoding='utf-8')
    
    # 重命名列
    df = df.rename(columns=COLUMN_MAPPING)
    
    # 处理日期格式
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
    
    # 提取纯数字代码 (000300.SH -> 000300)
    df['symbol'] = df['symbol'].str.extract(r'(\d{6})')
    
    # 按日期排序
    df = df.sort_values('date').reset_index(drop=True)
    
    # 保存为 Parquet
    df.to_parquet(output_file, index=False, compression='snappy')
    
    print(f"  Saved to {output_file.name}")
    print(f"  Rows: {len(df)}, Date range: {df['date'].min().date()} ~ {df['date'].max().date()}")
    print(f"  Columns: {list(df.columns)}")
    print()
    
    return df['date'].max()


def main():
    marketdata_dir = Path('data/marketdata')
    output_dir = Path('data/parquet_data')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    latest_dates = {}
    
    for csv_name, parquet_name in FILE_MAPPING.items():
        csv_file = marketdata_dir / csv_name
        parquet_file = output_dir / parquet_name
        
        if csv_file.exists():
            latest_date = convert_csv_to_parquet(csv_file, parquet_file)
            latest_dates[parquet_name] = latest_date
        else:
            print(f"Warning: {csv_file} not found")
    
    print("=" * 50)
    print("Conversion complete!")
    print("\nLatest dates:")
    for name, date in latest_dates.items():
        print(f"  {name}: {date.date()}")


if __name__ == '__main__':
    main()
