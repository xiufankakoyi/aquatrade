"""
检查is_st列的值分布
"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def check_is_st():
    print("检查is_st列...")
    
    query = OptimizedStockDataQuery()
    stock_info = query.get_stock_pool("2023-06-01")
    
    if stock_info is None or stock_info.empty:
        print("❌ 无数据")
        return
    
    print(f"\nis_st列统计:")
    print(stock_info['is_st'].value_counts())
    
    print(f"\nis_st列数据类型: {stock_info['is_st'].dtype}")
    
    # 检查是否有ST股票（通过股票名称判断）
    print(f"\n检查stock_info表是否有name列: {'name' in stock_info.columns}")
    
    # 检查原始parquet文件
    import polars as pl
    from pathlib import Path
    
    info_path = Path("data/parquet_data/stock_info.parquet")
    if info_path.exists():
        df = pl.read_parquet(info_path)
        print(f"\nstock_info.parquet列: {df.columns}")
        
        if 'is_st' in df.columns:
            print(f"\nis_st值分布:")
            print(df.group_by('is_st').agg(pl.len()).sort('is_st'))

if __name__ == "__main__":
    check_is_st()
