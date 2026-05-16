"""
调试数据加载流程
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

# 使用 OptimizedStockDataQuery
query = OptimizedStockDataQuery()

# 获取交易日期
dates = query.get_trading_dates()
print(f"交易日期: {len(dates)} 天")
print(f"范围: {dates[0] if dates else 'N/A'} ~ {dates[-1] if dates else 'N/A'}")

# 检查预加载数据
if hasattr(query, '_preloaded_data') and query._preloaded_data:
    print(f"\n预加载数据: {len(query._preloaded_data)} 个日期")
else:
    print("\n预加载数据: 无")

# 尝试预加载一小段数据
if len(dates) >= 10:
    test_start = dates[0]
    test_end = dates[9]
    print(f"\n尝试预加载: {test_start} ~ {test_end}")
    
    query.preload_backtest_data(test_start, test_end)
    
    preloaded = getattr(query, '_preloaded_data', None)
    if preloaded:
        print(f"预加载成功: {len(preloaded)} 个日期")
        first_date = list(preloaded.keys())[0]
        df = preloaded[first_date]
        print(f"第一个日期 {first_date}: {len(df)} 行")
        print(f"列名: {list(df.columns)[:10]}")
        if 'stock_code' in df.columns:
            codes = df['stock_code'].unique()[:10].tolist()
            print(f"股票代码示例: {codes}")
    else:
        print("预加载失败: 无数据")
