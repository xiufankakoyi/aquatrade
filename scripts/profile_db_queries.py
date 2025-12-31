"""
数据库性能定位脚本

用途：
- 包装 `OptimizedStockDataQuery`，记录每个数据库调用的耗时、调用次数
- 打印累计耗时排名，帮助识别“到底是 DB 的哪个环节慢了”

使用方式：
    python tools/profile_db_queries.py --strategy "策略名称" --start 2024-01-01 --end 2024-03-01
可选参数：
    --max-days 60            只统计前 N 个交易日（避免全周期过慢）
    --threshold 0.05         单次调用超过阈值(秒)时记录示例
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.optimized_backtest_engine import OptimizedBacktestEngine
from database.optimized_data_query import OptimizedStockDataQuery
from strategies.strategy_factory import get_factory


@dataclass
class CallStat:
    count: int = 0
    total: float = 0.0
    max_time: float = 0.0

    def update(self, duration: float) -> None:
        self.count += 1
        self.total += duration
        if duration > self.max_time:
            self.max_time = duration

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count else 0.0


class DataQueryProfiler:
    """
    对 OptimizedStockDataQuery 做一层动态代理，统计每个方法的耗时
    """

    def __init__(self, inner: OptimizedStockDataQuery, log_threshold: float = 0.05) -> None:
        self._inner = inner
        self.log_threshold = log_threshold
        self.stats: Dict[str, CallStat] = defaultdict(CallStat)
        self.samples: Dict[str, List[Tuple[float, Tuple[Any, ...], Dict[str, Any]]]] = defaultdict(list)
        self.date_stats: Dict[str, Dict[str, CallStat]] = defaultdict(lambda: defaultdict(CallStat))

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return attr(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                stat = self.stats[name]
                stat.update(duration)
                if duration >= self.log_threshold:
                    # 保存至多前 5 个慢调用示例
                    if len(self.samples[name]) < 5:
                        self.samples[name].append((duration, args, kwargs))

                if name == "get_stock_pool" and args:
                    date_key = str(args[0])
                    self.date_stats[name][date_key].update(duration)

        # 缓存包装后的方法，避免重复包装
        setattr(self, name, wrapper)
        return wrapper

    def print_report(self, top_n: int = 15) -> None:
        if not self.stats:
            print("未捕获到数据库调用，确认回测是否正常运行。")
            return

        print("\n" + "=" * 60)
        print("数据库调用耗时统计（按累计耗时排序）")
        print("=" * 60)
        rows = sorted(
            ((name, stat) for name, stat in self.stats.items()),
            key=lambda item: item[1].total,
            reverse=True,
        )
        header = f"{'方法':30} | {'次数':>6} | {'累计(s)':>9} | {'均值(ms)':>10} | {'最大(ms)':>10}"
        print(header)
        print("-" * len(header))
        for name, stat in rows[:top_n]:
            print(
                f"{name:30} | {stat.count:6d} | {stat.total:9.3f} | "
                f"{stat.avg * 1000:10.2f} | {stat.max_time * 1000:10.2f}"
            )

        print("\n慢调用示例（耗时 >= 阈值）")
        print("=" * 60)
        if not any(self.samples.values()):
            print("未记录到超过阈值的调用，可通过 --threshold 调整阈值。")
            return

        for name, entries in self.samples.items():
            print(f"\n{name}:")
            for duration, args, kwargs in entries:
                preview_args = ", ".join(repr(a) for a in args[:3])
                print(f"  - {duration:.3f}s args=({preview_args}...) kwargs={kwargs if kwargs else '{}'}")

        date_stats = self.date_stats.get("get_stock_pool")
        if date_stats:
            print("\n按日期统计 get_stock_pool 耗时（按最大耗时排序）")
            header = f"{'日期':12} | {'次数':>6} | {'累计(s)':>9} | {'均值(ms)':>10} | {'最大(ms)':>10}"
            print(header)
            print("-" * len(header))
            rows = sorted(date_stats.items(), key=lambda item: item[1].max_time, reverse=True)
            for date, stat in rows[:10]:
                print(
                    f"{date:12} | {stat.count:6d} | {stat.total:9.3f} | "
                    f"{stat.avg * 1000:10.2f} | {stat.max_time * 1000:10.2f}"
                )


def run_profile(strategy_name: str, start_date: str, end_date: str, max_days: Optional[int], threshold: float, top_n: int) -> None:
    profiler = DataQueryProfiler(OptimizedStockDataQuery(), log_threshold=threshold)
    engine = OptimizedBacktestEngine(profiler)
    strategy = get_factory().create_strategy(strategy_name)

    print(f"策略: {strategy_name}")
    print(f"周期: {start_date} -> {end_date}")
    print(f"慢调用阈值: {threshold:.3f}s")
    if max_days:
        print(f"仅统计前 {max_days} 个交易日")

    start = time.perf_counter()
    seen_dates = set()
    try:
        for update in engine.run_backtest_streaming(start_date, end_date, strategy):
            data = update.get("data") or {}
            date = data.get("date") or data.get("current_date")
            if date:
                seen_dates.add(date)
                if max_days and len(seen_dates) >= max_days:
                    break
            if update.get("type") == "error":
                print(f"回测报错: {data.get('message')}")
                break
            if update.get("type") == "final_metrics":
                break
    finally:
        elapsed = time.perf_counter() - start
        print(f"\n回测（截断）耗时: {elapsed:.3f}s, 覆盖交易日: {len(seen_dates)}")
        profiler.print_report(top_n=top_n)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回测数据库瓶颈定位脚本")
    parser.add_argument("--strategy", required=True, help="策略名称（与前端显示一致）")
    parser.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--max-days", type=int, default=None, help="仅统计前 N 个交易日，加快调试")
    parser.add_argument("--threshold", type=float, default=0.05, help="慢调用记录阈值（秒）")
    parser.add_argument("--top-n", type=int, default=15, help="报告中展示的函数数量")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_profile(args.strategy, args.start, args.end, args.max_days, args.threshold, args.top_n)


if __name__ == "__main__":
    main()


