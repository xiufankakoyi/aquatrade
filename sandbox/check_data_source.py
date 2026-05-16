"""
检查数据源 - 2025年数据是否存在
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_data():
    print("=" * 80)
    print("检查数据源")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    print("\n【检查交易日历】")
    dates = data_query.get_trading_dates('2025-01-01', '2025-01-31')
    print(f"2025年1月交易日: {len(dates)} 天")
    if dates:
        print(f"  前5天: {dates[:5]}")
        print(f"  后5天: {dates[-5:]}")
    
    print("\n【检查2025年1月股票池】")
    df = data_query.get_stock_pool('2025-01-15')
    if df is not None and not df.empty:
        print(f"2025-01-15 股票池: {len(df)} 只股票")
        print(f"列: {list(df.columns)[:10]}...")
        
        sample = df[df['stock_code'] == '600000']
        if not sample.empty:
            row = sample.iloc[0]
            print(f"\n600000 @ 2025-01-15:")
            print(f"  开盘: {row.get('open')}")
            print(f"  收盘: {row.get('close')}")
    else:
        print("2025-01-15 无数据")
    
    print("\n【检查2024年1月股票池作为对比】")
    df = data_query.get_stock_pool('2024-01-15')
    if df is not None and not df.empty:
        print(f"2024-01-15 股票池: {len(df)} 只股票")
        
        sample = df[df['stock_code'] == '600000']
        if not sample.empty:
            row = sample.iloc[0]
            print(f"\n600000 @ 2024-01-15:")
            print(f"  开盘: {row.get('open')}")
            print(f"  收盘: {row.get('close')}")
    
    print("\n【检查数据时间范围】")
    all_dates = data_query.get_trading_dates('2020-01-01', '2030-01-01')
    if all_dates:
        print(f"数据范围: {all_dates[0]} ~ {all_dates[-1]}")
        print(f"总交易日: {len(all_dates)}")


if __name__ == "__main__":
    check_data()
