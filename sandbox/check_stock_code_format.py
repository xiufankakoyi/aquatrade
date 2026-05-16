"""
检查预加载数据的 stock_code 格式
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_stock_code_format():
    print("=" * 80)
    print("检查预加载数据的 stock_code 格式")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    data_query.preload_backtest_data("2024-01-01", "2024-01-05")
    preloaded = getattr(data_query, '_preloaded_data', None)
    
    if preloaded is None:
        print("预加载数据为空")
        return
    
    first_date = list(preloaded.keys())[0]
    df = preloaded[first_date]
    
    print(f"\n第一个交易日: {first_date}")
    print(f"DataFrame 索引类型: {type(df.index)}")
    print(f"DataFrame 索引示例: {df.index[:5].tolist()}")
    
    if 'stock_code' in df.columns:
        print(f"\nstock_code 列类型: {df['stock_code'].dtype}")
        print(f"stock_code 示例: {df['stock_code'].head(5).tolist()}")
    else:
        print("\nstock_code 列不存在！")
        print(f"所有列: {df.columns.tolist()}")
    
    print(f"\nset_index('stock_code') 后的索引示例:")
    if 'stock_code' in df.columns:
        indexed = df.set_index('stock_code')
        print(f"  索引类型: {type(indexed.index)}")
        print(f"  索引示例: {indexed.index[:5].tolist()}")
        
        print(f"\nto_dict('index') 的键示例:")
        d = indexed.to_dict('index')
        keys = list(d.keys())[:5]
        print(f"  键: {keys}")


if __name__ == "__main__":
    check_stock_code_format()
