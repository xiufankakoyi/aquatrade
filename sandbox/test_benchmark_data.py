"""
测试基准数据
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
from server.services.stock_data_service import StockDataService
from server.services.data_initialization_service import DataInitializationService

def test_benchmark_data():
    print("=" * 80)
    print("测试基准数据")
    print("=" * 80)
    
    init_service = DataInitializationService()
    init_service.ensure_initialized()
    
    stock_data_service = StockDataService(init_service)
    
    benchmark_code = '000300'
    start_date = '2024-01-01'
    end_date = '2024-03-31'
    
    # 获取基准数据
    print(f"\n[1] 获取基准数据: {benchmark_code}, {start_date} ~ {end_date}")
    benchmark_df = stock_data_service.get_benchmark_data_from_db(benchmark_code, start_date, end_date)
    print(f"  基准数据行数: {len(benchmark_df)}")
    if not benchmark_df.empty:
        print(f"  日期范围: {benchmark_df['date'].iloc[0]} ~ {benchmark_df['date'].iloc[-1]}")
        print(f"  前5行:")
        print(benchmark_df.head())
        print(f"  后5行:")
        print(benchmark_df.tail())
    
    # 获取策略交易日期
    print(f"\n[2] 获取策略交易日期")
    dates = init_service.data_query.get_trading_dates(start_date, end_date)
    print(f"  交易日期数: {len(dates)}")
    print(f"  前5个: {dates[:5]}")
    print(f"  后5个: {dates[-5:]}")
    
    # 合并数据
    print(f"\n[3] 合并数据")
    strategy_dates_df = pd.DataFrame({'date': dates})
    merged_df = pd.merge(strategy_dates_df, benchmark_df, on='date', how='left')
    
    print(f"  合并后行数: {len(merged_df)}")
    print(f"  close 列空值数: {merged_df['close'].isna().sum()}")
    
    # 检查空值分布
    if merged_df['close'].isna().sum() > 0:
        print(f"\n  [WARN] 存在空值，检查空值位置:")
        na_rows = merged_df[merged_df['close'].isna()]
        print(f"  空值日期: {na_rows['date'].tolist()[:10]}")
    
    # 填充空值
    merged_df['close'] = merged_df['close'].ffill().bfill()
    
    # 标准化
    initial_capital = 1_000_000
    first_valid_benchmark = merged_df['close'].dropna().iloc[0]
    print(f"\n[4] 标准化基准曲线")
    print(f"  首个有效基准值: {first_valid_benchmark}")
    
    normalized_curve = (merged_df['close'] / first_valid_benchmark) * initial_capital
    benchmark_curve = normalized_curve.fillna(initial_capital).tolist()
    
    print(f"  基准曲线长度: {len(benchmark_curve)}")
    print(f"  前10个值: {benchmark_curve[:10]}")
    print(f"  后10个值: {benchmark_curve[-10:]}")
    
    # 检查是否有跳跃
    print(f"\n[5] 检查数据跳跃")
    changes = []
    for i in range(1, len(benchmark_curve)):
        change = (benchmark_curve[i] - benchmark_curve[i-1]) / benchmark_curve[i-1] * 100
        changes.append(change)
        if abs(change) > 2:  # 单日变化超过 2%
            print(f"  [WARN] 大跳跃: 第{i}天, 变化 {change:.2f}%")
    
    print(f"\n  日变化统计:")
    print(f"    最大涨幅: {max(changes):.2f}%")
    print(f"    最大跌幅: {min(changes):.2f}%")
    print(f"    平均变化: {sum(changes)/len(changes):.4f}%")

if __name__ == '__main__':
    test_benchmark_data()
