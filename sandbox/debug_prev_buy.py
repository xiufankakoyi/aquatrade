"""
检查前一交易日数据是否符合买入条件
"""
import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def check_prev_day_buy():
    print("=" * 80)
    print("检查前一交易日数据是否符合买入条件")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    prev_date = "2023-12-29"
    df = data_query.get_stock_pool(prev_date)
    
    if df is None or df.empty:
        print(f"无法获取 {prev_date} 的数据")
        return
    
    print(f"\n{prev_date} 数据行数: {len(df)}")
    
    required_cols = ['ma5', 'ma10', 'ma20', 'close']
    df = df.dropna(subset=required_cols)
    print(f"去除NaN后行数: {len(df)}")
    
    if 'is_st' in df.columns:
        df = df[df['is_st'] == 0]
        print(f"去除ST后行数: {len(df)}")
    
    if 'list_days' in df.columns:
        df = df[df['list_days'] >= 60]
        print(f"上市>=60天后行数: {len(df)}")
    
    if 'total_mv' in df.columns:
        market_cap_min = 20 * 100_000_000
        market_cap_max = 5000 * 100_000_000
        df = df[(df['total_mv'] >= market_cap_min) & (df['total_mv'] <= market_cap_max)]
        print(f"市值过滤后行数: {len(df)}")
    
    trend_ok = (
        (df['ma5'] > df['ma10']) &
        (df['ma10'] > df['ma20'])
    )
    print(f"趋势OK行数: {trend_ok.sum()}")
    
    price_above = df['close'] > df['ma5']
    print(f"价格在MA5上方行数: {price_above.sum()}")
    
    volume_ok = True
    if 'volume_ratio' in df.columns:
        volume_ok = df['volume_ratio'] >= 1.0
        print(f"量比>=1.0行数: {volume_ok.sum()}")
    
    bias_ok = (df['close'] / df['ma5'] - 1) < 0.10
    print(f"乖离率<10%行数: {bias_ok.sum()}")
    
    final_mask = trend_ok & price_above & volume_ok & bias_ok
    print(f"\n最终符合条件的行数: {final_mask.sum()}")
    
    if final_mask.sum() > 0:
        candidates = df.loc[final_mask, ['stock_code', 'close', 'ma5', 'ma10', 'ma20', 'volume_ratio']].head(10)
        print("\n候选股票:")
        print(candidates.to_string())


if __name__ == "__main__":
    check_prev_day_buy()
