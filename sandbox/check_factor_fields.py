"""
检查预加载数据中的因子字段
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_factor_fields():
    print("=" * 80)
    print("检查预加载数据中的因子字段")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    print(f"\n预加载区间: {start_date} ~ {end_date}")
    
    data_query.preload_backtest_data(start_date, end_date)
    
    preloaded = getattr(data_query, '_preloaded_data', None)
    
    if preloaded is None or len(preloaded) == 0:
        print("预加载数据为空")
        return
    
    first_date = list(preloaded.keys())[0]
    df = preloaded[first_date]
    
    print(f"\n第一个交易日: {first_date}")
    print(f"数据形状: {df.shape}")
    print(f"\n所有字段 ({len(df.columns)} 个):")
    
    factor_fields = ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250',
                     'close', 'open', 'high', 'low', 'volume', 'amount',
                     'total_mv', 'is_st', 'volume_ratio', 'turnover_rate',
                     'rsi_14', 'kdj_k', 'macd_dif', 'boll_upper']
    
    print("\n因子字段检查:")
    for field in factor_fields:
        if field in df.columns:
            sample = df[field].dropna().head(3).tolist()
            print(f"  ✓ {field}: {sample}")
        else:
            print(f"  ✗ {field}: 缺失")
    
    print("\n所有列名:")
    print(df.columns.tolist())


if __name__ == "__main__":
    check_factor_fields()
