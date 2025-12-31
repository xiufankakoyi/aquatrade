import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, Tuple

# 将项目根目录加入路径，便于脚本直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.optimized_backtest_engine import OptimizedBacktestEngine
from database.optimized_data_query import OptimizedStockDataQuery
from strategies.strategy_factory import get_factory
from utils.config import Config

# === 固定配置 ===
STRATEGY_NAME = "聚宽量比市值策略V3_严格趋势"
START_DATE = "2024-05-27"
END_DATE = "2025-01-17"

POP_SIZE = 20  # 种群大小
N_GEN = 20  # 迭代次数
N_WORKERS = max(os.cpu_count() - 1, 1)  # 并行进程数

# 策略参数搜索空间（根据 SimpleVolumeStrategyV3 的构造参数设置）
PARAM_SPACE: Dict[str, Tuple[float, float]] = {
    "volume_ratio_threshold": (1.5, 5.0),
    "turnover_rate_threshold": (1.0, 5.0),
    "market_cap_min": (10 * 10_000, 120 * 10_000),
    "market_cap_max": (120 * 10_000, 320 * 10_000),
    "position_ratio": (0.05, 0.35),
    "max_stocks_per_day": (1, 6),  # 整数参数，稍后取整
    "bank_position_ratio": (0.5, 1.5),
    "bank_safe_ma": (10, 40),  # 整数参数，稍后取整
    "max_candidates": (300, 2000),  # 整数参数，稍后取整
}

# 全局引擎缓存（每个进程内独立的一份）
_ENGINE_CACHE: Dict[str, Any] | None = None


def _normalize_params(raw_params: Dict[str, float]) -> Dict[str, Any]:
    """
    清洗/裁剪参数，确保满足策略入参要求。
    - 连续型直接取浮点数
    - 部分参数需要取整
    - 确保市值下/上限有序
    - 限制仓位比例在 0~1 之间
    """
    params: Dict[str, Any] = dict(raw_params)

    # 强制整数的参数
    for key in ("max_stocks_per_day", "bank_safe_ma", "max_candidates"):
        if key in params:
            params[key] = int(max(1, round(params[key])))

    # 市值区间矫正
    min_mv = float(params.get("market_cap_min", PARAM_SPACE["market_cap_min"][0]))
    max_mv = float(params.get("market_cap_max", PARAM_SPACE["market_cap_max"][0]))
    if max_mv <= min_mv:
        max_mv = min_mv + 10_000  # 至少相差 1 亿市值（以万为单位）
    params["market_cap_min"] = min_mv
    params["market_cap_max"] = max_mv

    # 仓位比例限制在 0~1 之间
    if "position_ratio" in params:
        params["position_ratio"] = max(0.0, min(1.0, float(params["position_ratio"])))

    # 其他浮点参数统一转为 float
    for key in ("volume_ratio_threshold", "turnover_rate_threshold", "bank_position_ratio"):
        if key in params:
            params[key] = float(params[key])

    return params


def init_worker() -> None:
    """
    每个进程启动时调用一次：
    - 创建回测引擎
    - 预加载指定区间的数据
    之后这个进程里所有个体评估都重用这份引擎和数据
    """
    global _ENGINE_CACHE
    if _ENGINE_CACHE is not None:
        return

    data_query = OptimizedStockDataQuery(warmup=True)
    engine = OptimizedBacktestEngine(
        data_query=data_query,
        initial_capital=Config.INITIAL_CAPITAL,
    )

    # 预加载（只在这个进程里第一次做一次）
    try:
        data_query.preload_backtest_data(START_DATE, END_DATE)
    except Exception as exc:  # 预加载失败不致命，继续后续查询
        print(f"[Worker] 预加载失败: {exc}")

    _ENGINE_CACHE = {"engine": engine, "factory": get_factory()}
    print(f"[Worker] 引擎初始化完成，并已预加载 {START_DATE} ~ {END_DATE}")


def compute_fitness(metrics: Dict[str, float]) -> float:
    """
    计算 GA 适应度（值越大越好）
    当前策略：兼顾收益与回撤/夏普
    """
    annualized = float(metrics.get("annualizedReturn", 0.0))
    sharpe = float(metrics.get("sharpeRatio", 0.0))
    drawdown = float(metrics.get("maxDrawdown", 0.0))

    # 基础思路：收益 + 夏普奖励 - 回撤惩罚
    return annualized + sharpe * 2.0 - drawdown * 0.6


def run_single_backtest(
    param_dict: Dict[str, float],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Tuple[float, Dict[str, float]]:
    """
    跑一遍回测并返回适应度和完整指标
    """
    global _ENGINE_CACHE
    if _ENGINE_CACHE is None:
        init_worker()
    if _ENGINE_CACHE is None:
        raise RuntimeError("Engine initialization failed")

    engine: OptimizedBacktestEngine = _ENGINE_CACHE["engine"]
    factory = _ENGINE_CACHE["factory"]

    strategy_params = _normalize_params(param_dict)
    strategy = factory.create_strategy(STRATEGY_NAME, **strategy_params)

    final_metrics: Dict[str, float] | None = None
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        event_type = update.get("type")
        if event_type == "final_metrics":
            final_metrics = update.get("data", {})
        elif event_type == "error":
            msg = (update.get("data") or {}).get("message", "unknown error")
            print(f"[Backtest] 发生错误: {msg}")
            return float("-inf"), {}

    if not final_metrics:
        return float("-inf"), {}

    fitness = compute_fitness(final_metrics)
    return fitness, final_metrics


def run_backtest_with_params(param_dict: Dict[str, float]) -> float:
    """
    在单个进程内，被并行调用：
    - 用全局 _ENGINE_CACHE 跑一遍回测
    - 返回一个“越大越好”的评分作为 GA fitness
    """
    score, _ = run_single_backtest(param_dict)
    return score


if __name__ == "__main__":
    # 简单冒烟：用参数空间中点跑一遍，打印指标和 fitness
    center_params = {
        key: (low + high) / 2 for key, (low, high) in PARAM_SPACE.items()
    }
    fitness, metrics = run_single_backtest(center_params)
    print(f"Center params fitness: {fitness:.4f}")
    print("Metrics:", metrics)
