"""
调试 _preload_data 返回值
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
import pandas as pd

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)

start_date = '2025-06-03'
end_date = '2025-06-10'

start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# 预加载数据
preloaded_data = engine._preload_data(start_ts, end_ts)

print(f"_preload_data 返回值类型: {type(preloaded_data)}")
print(f"_preload_data 是否为 None: {preloaded_data is None}")

if preloaded_data is not None:
    print(f"_preload_data 键: {list(preloaded_data.keys())[:5]}...")
    print(f"_preload_data 键数量: {len(preloaded_data)}")
    
    # 检查是否有 'stock_daily' 键
    if 'stock_daily' in preloaded_data:
        print(f"'stock_daily' 存在！")
        stock_daily = preloaded_data['stock_daily']
        print(f"  类型: {type(stock_daily)}")
        if hasattr(stock_daily, '__len__'):
            print(f"  长度: {len(stock_daily)}")
    else:
        print(f"'stock_daily' 不存在！")
        # 检查第一个键的值
        first_key = list(preloaded_data.keys())[0]
        first_value = preloaded_data[first_key]
        print(f"  第一个键: {first_key}")
        print(f"  第一个值类型: {type(first_value)}")
