"""
检查 LanceDB 数据库结构
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import lancedb

def check_db_structure():
    db_path = Path(__file__).parent.parent / "data" / "lancedb"
    db = lancedb.connect(str(db_path))
    
    print("=" * 60)
    print("LanceDB 数据库结构")
    print("=" * 60)
    
    print("\n可用表:")
    tables = db.table_names()
    for t in tables:
        print(f"  - {t}")
    
    if 'daily_ohlcv' in tables:
        table = db.open_table('daily_ohlcv')
        df = table.to_arrow()
        df_pl = pl.from_arrow(df)
        
        print(f"\n[daily_ohlcv] 表结构:")
        print(f"  行数: {len(df_pl):,}")
        print(f"  列数: {len(df_pl.columns)}")
        print(f"  列名: {df_pl.columns}")
        print(f"  内存: {df_pl.estimated_size() / (1024*1024):.1f} MB")
        
        print(f"\n  数据类型:")
        for col in df_pl.columns[:10]:
            print(f"    {col}: {df_pl[col].dtype}")
    
    if 'stock_info' in tables:
        table = db.open_table('stock_info')
        df = table.to_arrow()
        df_pl = pl.from_arrow(df)
        
        print(f"\n[stock_info] 表结构:")
        print(f"  行数: {len(df_pl):,}")
        print(f"  列数: {len(df_pl.columns)}")
        print(f"  列名: {df_pl.columns}")


if __name__ == "__main__":
    check_db_structure()
