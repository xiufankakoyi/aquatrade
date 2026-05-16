"""
检查回测引擎实际使用的数据源
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
print(f"交易日期范围: {dates[0] if dates else 'N/A'} ~ {dates[-1] if dates else 'N/A'}")
print(f"总交易日数: {len(dates)}")

# 预加载数据
if dates:
    query.preload_backtest_data(dates[0], dates[-1])
    preloaded = getattr(query, '_preloaded_data', None)
    
    if preloaded:
        print(f"\n预加载数据: {len(preloaded)} 个日期")
        first_date = list(preloaded.keys())[0]
        df = preloaded[first_date]
        print(f"第一个日期 {first_date}: {len(df)} 行")
        print(f"列名: {df.columns[:10].tolist()}...")
