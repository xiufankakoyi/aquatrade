"""
性能分析工具 - 用于回测系统的性能分析

支持两种分析模式：
1. cProfile - 函数级别的性能分析
2. line_profiler - 逐行性能分析（需要 @profile 装饰器）

使用方法：
    python tools/profile_backtest.py --strategy "策略名称" --start "2024-01-01" --end "2024-12-31"
    python tools/profile_backtest.py --strategy "策略名称" --start "2024-01-01" --end "2024-12-31" --line-profile
"""

import cProfile
import pstats
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
import argparse

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from database.optimized_data_query import OptimizedStockDataQuery
from backtest.optimized_backtest_engine import OptimizedBacktestEngine
from strategies.strategy_factory import get_factory
from utils.config import Config


def profile_backtest_with_cprofile(
    strategy_name: str,
    start_date: str,
    end_date: str,
    output_file: Optional[str] = None,
    top_n: int = 30,
) -> Dict[str, Any]:
    """
    使用 cProfile 进行函数级别的性能分析
    
    Args:
        strategy_name: 策略名称
        start_date: 开始日期
        end_date: 结束日期
        output_file: 输出文件路径（可选）
        top_n: 显示前 N 个最耗时的函数
        
    Returns:
        性能统计信息
    """
    print("=" * 60)
    print("开始性能分析 (cProfile)")
    print("=" * 60)
    print(f"策略: {strategy_name}")
    print(f"日期范围: {start_date} 到 {end_date}")
    print()
    
    # 初始化组件
    data_query = OptimizedStockDataQuery()
    engine = OptimizedBacktestEngine(data_query)
    factory = get_factory()
    strategy = factory.create_strategy(strategy_name)
    
    # 创建 profiler
    profiler = cProfile.Profile()
    
    # 开始分析
    start_time = time.perf_counter()
    profiler.enable()
    
    try:
        # 运行回测（只运行一次，不流式输出）
        results = []
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            if update.get("type") == "final_metrics":
                results.append(update.get("data", {}))
            elif update.get("type") == "error":
                print(f"回测错误: {update.get('data', {}).get('message', 'Unknown error')}")
                return {}
    except Exception as e:
        print(f"回测执行失败: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        profiler.disable()
        elapsed = time.perf_counter() - start_time
    
    print(f"\n回测总耗时: {elapsed:.3f} 秒")
    print()
    
    # 分析结果
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    
    # 输出到控制台
    print("=" * 60)
    print(f"Top {top_n} 最耗时的函数 (按累计时间排序):")
    print("=" * 60)
    stats.print_stats(top_n)
    
    # 输出到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            stats.print_stats(file=f)
        print(f"\n详细报告已保存到: {output_file}")
    
    # 生成调用图统计
    print("\n" + "=" * 60)
    print("调用统计 (按调用次数排序):")
    print("=" * 60)
    stats.sort_stats('ncalls')
    stats.print_stats(20)
    
    # 提取关键指标
    total_time = stats.total_tt
    key_functions = []
    for func_info in stats.stats:
        func_name = pstats.func_std_string(func_info)
        call_count, total_time_func, cumulative_time, _ = stats.stats[func_info][:4]
        if cumulative_time > 0.1:  # 只记录累计时间超过 0.1 秒的函数
            key_functions.append({
                'function': func_name,
                'calls': call_count,
                'total_time': total_time_func,
                'cumulative_time': cumulative_time,
                'time_percent': (cumulative_time / total_time) * 100 if total_time > 0 else 0,
            })
    
    # 按累计时间排序
    key_functions.sort(key=lambda x: x['cumulative_time'], reverse=True)
    
    return {
        'total_time': total_time,
        'elapsed_time': elapsed,
        'key_functions': key_functions[:top_n],
    }


def profile_with_line_profiler(
    strategy_name: str,
    start_date: str,
    end_date: str,
) -> None:
    """
    使用 line_profiler 进行逐行性能分析
    
    注意：需要在要分析的函数上添加 @profile 装饰器
    """
    try:
        from line_profiler import LineProfiler
    except ImportError:
        print("错误: 未安装 line_profiler")
        print("请运行: pip install line_profiler")
        return
    
    print("=" * 60)
    print("开始逐行性能分析 (line_profiler)")
    print("=" * 60)
    print(f"策略: {strategy_name}")
    print(f"日期范围: {start_date} 到 {end_date}")
    print()
    print("注意: 需要在要分析的函数上添加 @profile 装饰器")
    print()
    
    # 创建 profiler
    profiler = LineProfiler()
    
    # 添加要分析的函数
    from database.optimized_data_query import OptimizedStockDataQuery
    from backtest.optimized_backtest_engine import OptimizedBacktestEngine
    
    # 包装关键函数
    profiler.add_function(OptimizedStockDataQuery.get_stock_pool)
    profiler.add_function(OptimizedBacktestEngine.run_backtest_streaming)
    
    # 初始化组件
    data_query = OptimizedStockDataQuery()
    engine = OptimizedBacktestEngine(data_query)
    factory = get_factory()
    strategy = factory.create_strategy(strategy_name)
    
    # 运行分析
    start_time = time.perf_counter()
    profiler.enable()
    
    try:
        count = 0
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            count += 1
            if count > 10:  # 只分析前 10 天的数据
                break
    finally:
        profiler.disable()
        elapsed = time.perf_counter() - start_time
    
    print(f"\n分析耗时: {elapsed:.3f} 秒")
    print()
    
    # 输出结果
    profiler.print_stats()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='回测性能分析工具')
    parser.add_argument('--strategy', type=str, required=True, help='策略名称')
    parser.add_argument('--start', type=str, required=True, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, help='输出文件路径（可选）')
    parser.add_argument('--top-n', type=int, default=30, help='显示前 N 个函数（默认: 30）')
    parser.add_argument('--line-profile', action='store_true', help='使用 line_profiler 进行逐行分析')
    
    args = parser.parse_args()
    
    if args.line_profile:
        profile_with_line_profiler(args.strategy, args.start, args.end)
    else:
        result = profile_backtest_with_cprofile(
            args.strategy,
            args.start,
            args.end,
            args.output,
            args.top_n,
        )
        
        # 输出摘要
        if result:
            print("\n" + "=" * 60)
            print("性能分析摘要")
            print("=" * 60)
            print(f"总耗时: {result['elapsed_time']:.3f} 秒")
            print(f"关键函数数量: {len(result['key_functions'])}")
            print("\nTop 5 最耗时的函数:")
            for i, func in enumerate(result['key_functions'][:5], 1):
                print(f"{i}. {func['function']}")
                print(f"   累计时间: {func['cumulative_time']:.3f}s ({func['time_percent']:.1f}%)")
                print(f"   调用次数: {func['calls']}")


if __name__ == "__main__":
    main()

