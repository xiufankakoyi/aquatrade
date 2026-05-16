"""
检查起始权益异常问题
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.simple_volume_v3 import SimpleVolumeStrategyV3
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_initial_equity():
    print("=" * 80)
    print("检查起始权益异常")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    engine = UnifiedBacktestEngine(data_query)
    
    print(f"\n引擎配置:")
    print(f"  initial_capital: {engine.config.initial_capital}")
    print(f"  commission_rate: {engine.config.commission_rate}")
    print(f"  min_commission: {engine.config.min_commission}")
    
    strategy = SimpleVolumeStrategyV3()
    
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    print(f"\n测试 2024-01-01 ~ 2024-01-31:")
    
    first_equity = None
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        update_type = update.get('type')
        data = update.get('data', {})
        
        if update_type == 'backtest_start':
            print(f"\nbacktest_start: {data}")
        
        if update_type == 'daily_equity_engine':
            if first_equity is None:
                first_equity = data
                print(f"\n第一笔权益记录:")
                print(f"  date: {data.get('date')}")
                print(f"  equity: {data.get('equity')}")
                print(f"  cash: {data.get('cash')}")
                print(f"  positions: {data.get('positions')}")
    
    print("\n" + "=" * 80)
    print("检查股票池第一个交易日的数据")
    print("=" * 80)
    
    dates = data_query.get_trading_dates('2024-01-01', '2024-01-10')
    print(f"\n2024年1月前几个交易日: {dates}")
    
    if dates:
        first_date = dates[0]
        df = data_query.get_stock_pool(first_date)
        if df is not None:
            print(f"\n{first_date} 股票池:")
            print(f"  股票数: {len(df)}")
            
            sample = df[df['stock_code'] == '600000']
            if not sample.empty:
                row = sample.iloc[0]
                print(f"\n  600000 数据:")
                for col in ['open', 'close', 'adj_factor']:
                    if col in row:
                        print(f"    {col}: {row[col]}")


if __name__ == "__main__":
    check_initial_equity()
