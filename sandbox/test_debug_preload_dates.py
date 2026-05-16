"""
调试_preload_data方法中的日期参数
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
from datetime import datetime, timedelta
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig

print("=" * 70)
print("调试_preload_data方法中的日期参数")
print("=" * 70)

try:
    # 初始化
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    config = BacktestConfig()
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    # 模拟run_backtest中的日期转换
    start_date = '2025-01-01'
    end_date = '2025-01-31'
    
    start_ts = engine._normalize_datetime(start_date)
    end_ts = engine._normalize_datetime(end_date)
    
    print(f"\n[2] 日期转换:")
    print(f"  start_date: {start_date}")
    print(f"  start_ts: {start_ts}")
    print(f"  end_date: {end_date}")
    print(f"  end_ts: {end_ts}")
    
    # 模拟_preload_data中的日期计算
    load_end_str = end_ts.strftime("%Y-%m-%d")
    print(f"\n[3] _preload_data中的日期参数:")
    print(f"  load_end_str: {load_end_str}")
    
    # 计算warmup_start_str
    warmup_days = config.warmup_days
    print(f"  warmup_days: {warmup_days}")
    
    hist_dates = data_query.get_trading_dates(
        (start_ts - timedelta(days=60)).strftime("%Y-%m-%d"),
        (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
    )
    print(f"  hist_dates数量: {len(hist_dates)}")
    print(f"  hist_dates前5: {hist_dates[:5]}")
    print(f"  hist_dates后5: {hist_dates[-5:]}")
    
    if len(hist_dates) >= warmup_days:
        warmup_start_str = hist_dates[-warmup_days]
    elif hist_dates:
        warmup_start_str = hist_dates[0]
    else:
        warmup_start_str = start_ts.strftime("%Y-%m-%d")
    
    print(f"  warmup_start_str: {warmup_start_str}")
    
    # 计算actual_start
    try:
        prev_trading_dates = data_query.get_trading_dates(
            (start_ts - timedelta(days=10)).strftime("%Y-%m-%d"),
            (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
        )
        if prev_trading_dates:
            actual_start = prev_trading_dates[-1]
        else:
            actual_start = start_ts.strftime("%Y-%m-%d")
    except Exception:
        actual_start = (start_ts - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"  actual_start: {actual_start}")
    
    # 检查UnifiedDataManager.read的调用参数
    print(f"\n[4] UnifiedDataManager.read调用参数:")
    print(f"  library: stock_daily")
    print(f"  start_date: {warmup_start_str}")
    print(f"  end_date: {load_end_str}")
    
    # 实际调用read方法
    from data_svc.unified_data_manager import get_unified_manager
    manager = get_unified_manager()
    df = manager.read('stock_daily', start_date=warmup_start_str, end_date=load_end_str, use_cache=False)
    
    print(f"\n[5] 读取结果:")
    print(f"  数据条数: {len(df)}")
    
    if not df.is_empty() and 'trade_date' in df.columns:
        dates = df['trade_date'].unique().sort().to_list()
        print(f"  日期数量: {len(dates)}")
        print(f"  开始日期: {dates[0]}")
        print(f"  结束日期: {dates[-1]}")
        print(f"\n  所有日期:")
        for d in dates:
            print(f"    {d}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
