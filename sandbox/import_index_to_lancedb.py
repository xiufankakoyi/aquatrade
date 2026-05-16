"""
将指数CSV数据导入到LanceDB
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import lancedb
import polars as pl

def import_index_to_lancedb():
    """导入指数数据到LanceDB"""
    
    data_dir = Path(r"C:\Users\Liu\Desktop\projects\aquatrade\data\marketdata")
    db_path = Path(__file__).parent.parent / "data" / "lancedb"
    
    db = lancedb.connect(str(db_path))
    
    index_files = {
        '000001': '上证指数',
        '000016': '上证50',
        '000300': '沪深300',
        '000905': '中证500',
        '399001': '深证成指',
        '399006': '创业板指',
    }
    
    # 中文列名映射
    col_mapping = {
        '交易日期': 'trade_date',
        '开盘价': 'open',
        '最高价': 'high',
        '最低价': 'low',
        '收盘价': 'close',
        '成交量(手)': 'volume',
        '成交额(万元)': 'amount',
    }
    
    all_data = []
    
    for code, name in index_files.items():
        csv_path = data_dir / f"{code}.csv"
        if not csv_path.exists():
            print(f"文件不存在: {csv_path}")
            continue
        
        print(f"读取 {name} ({code})...")
        df = pd.read_csv(csv_path)
        
        print(f"  原始列: {df.columns.tolist()[:5]}...")
        print(f"  行数: {len(df)}")
        
        # 重命名列
        df = df.rename(columns=col_mapping)
        
        if 'trade_date' not in df.columns or 'close' not in df.columns:
            print(f"  缺少必要列，跳过")
            continue
        
        # 添加symbol和name
        df['symbol'] = code + '.SH' if code.startswith('0') else code + '.SZ'
        df['name'] = name
        
        # 转换日期
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        else:
            df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str))
        
        # 只保留需要的列
        keep_cols = ['trade_date', 'symbol', 'name', 'close', 'open', 'high', 'low', 'volume', 'amount']
        df = df[[c for c in keep_cols if c in df.columns]]
        
        all_data.append(df)
        print(f"  处理后行数: {len(df)}")
    
    if not all_data:
        print("没有数据可导入")
        return
    
    # 合并所有数据
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n总数据行数: {len(combined)}")
    
    # 转换为Polars
    combined_pl = pl.from_pandas(combined)
    
    # 写入LanceDB
    table_name = 'index_daily'
    
    if table_name in db.table_names():
        print(f"删除旧表: {table_name}")
        db.drop_table(table_name)
    
    db.create_table(table_name, combined_pl)
    print(f"创建新表: {table_name}")
    
    # 验证
    table = db.open_table(table_name)
    print(f"表中行数: {table.count_rows()}")
    
    # 显示symbols
    sample = pl.from_arrow(table.to_arrow())
    symbols = sample.select('symbol', 'name').unique()
    print(f"\n可用指数:")
    for row in symbols.iter_rows(named=True):
        print(f"  {row['symbol']}: {row['name']}")


if __name__ == "__main__":
    import_index_to_lancedb()
