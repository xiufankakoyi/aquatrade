#!/usr/bin/env python3
"""
验证服务层的基准曲线是否正确
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_service_benchmark():
    print("=" * 80)
    print("验证服务层基准曲线")
    print("=" * 80)
    
    from server.services.data_initialization_service import DataInitializationService
    from server.services.metrics_service import MetricsService
    from server.services.stock_data_service import StockDataService
    from server.services.backtest_service import BacktestService
    
    init_service = DataInitializationService()
    stock_data_service = StockDataService(init_service)
    metrics_service = MetricsService(init_service, stock_data_service)
    backtest_service = BacktestService(init_service, metrics_service, stock_data_service)
    
    strategy_name = "simple_test"
    start_date = "2024-01-01"
    end_date = "2024-03-31"
    benchmark_code = "000300"
    
    print(f"\n[1] 运行流式回测: {strategy_name}")
    print(f"    日期范围: {start_date} ~ {end_date}")
    print(f"    基准代码: {benchmark_code}")
    print("-" * 60)
    
    final_data = None
    for update in backtest_service.stream_backtest(
        strategy_name, start_date, end_date, benchmark_code
    ):
        if update.get('type') == 'stream_complete':
            final_data = update.get('data', {})
            break
        elif update.get('type') == 'error':
            print(f"  [ERROR] {update.get('data', {}).get('message')}")
            return
    
    if not final_data:
        print("  [ERROR] 未收到最终数据")
        return
    
    print(f"\n[2] 检查基准曲线")
    print("-" * 60)
    
    benchmark_curve = final_data.get('benchmarkCurve', [])
    print(f"  基准曲线点数: {len(benchmark_curve)}")
    
    if benchmark_curve:
        print(f"  前3个: {benchmark_curve[:3]}")
        print(f"  后3个: {benchmark_curve[-3:]}")
        
        first_equity = benchmark_curve[0].get('equity', 0)
        last_equity = benchmark_curve[-1].get('equity', 0)
        
        print(f"\n  首日归一化值: {first_equity:,.2f}")
        print(f"  末日归一化值: {last_equity:,.2f}")
        print(f"  基准收益率: {(last_equity - first_equity) / first_equity * 100:.2f}%")
        
        dates = [p['date'] for p in benchmark_curve]
        unique_dates = set(dates)
        print(f"\n  日期数量: {len(dates)}, 唯一日期数量: {len(unique_dates)}")
        
        if len(dates) != len(unique_dates):
            print("  [WARN] 存在重复日期!")
            from collections import Counter
            date_counts = Counter(dates)
            duplicates = {d: c for d, c in date_counts.items() if c > 1}
            print(f"  重复日期示例: {list(duplicates.items())[:5]}")
        else:
            print("  [OK] 无重复日期")
    
    print(f"\n[3] 检查权益曲线")
    print("-" * 60)
    
    equity_curve = final_data.get('equityCurve', [])
    print(f"  权益曲线点数: {len(equity_curve)}")
    
    if equity_curve:
        print(f"  前3个: {equity_curve[:3]}")
        print(f"  后3个: {equity_curve[-3:]}")
    
    print(f"\n[4] 检查月度收益数据")
    print("-" * 60)
    
    monthly_returns = final_data.get('monthlyReturns', [])
    print(f"  月度收益数据条数: {len(monthly_returns)}")
    
    if monthly_returns:
        print(f"  数据格式示例: {monthly_returns[0]}")
        
        for mr in monthly_returns:
            year = mr.get('year')
            months = mr.get('months', [])
            print(f"\n  {year}年:")
            for i, val in enumerate(months):
                if val is not None:
                    print(f"    {i+1}月: {val}%")
    
    print("\n" + "=" * 80)
    print("验证完成")
    print("=" * 80)

if __name__ == "__main__":
    test_service_benchmark()
