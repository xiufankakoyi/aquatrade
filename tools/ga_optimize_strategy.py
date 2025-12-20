"""
GA 参数优化脚本（结合 VisualizationAPI / OptimizedBacktestEngine）

用法示例：
    python tools/ga_optimize_strategy.py ^
        --strategy "聚宽量比市值策略V3_严格趋势" ^
        --start 2024-05-27 ^
        --end 2025-01-17 ^
        --pop-size 20 ^
        --generations 20 ^
        --workers 4 ^
        --db-path database/stock_data.db

说明：
- 单进程模式下：主进程预加载一次数据，GA 串行评估。
- 多进程模式下：每个子进程各自创建 OptimizedStockDataQuery + Engine，并预加载一次，
  然后在各自进程里反复跑回测（适合长时间 GA，利用多核 CPU）。
- 使用 VisualizationAPI.get_strategy_params 自动拿参数定义。
- 当前目标函数：最大化 totalReturn（%）。
"""

import argparse
import os
import random
import time
import logging
from typing import Any, Dict, List, Tuple, Optional
import sys
import pathlib
from concurrent.futures import ProcessPoolExecutor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 将项目根目录加入 sys.path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from visualization_api import BacktestVisualizationAPI  # 你已有的文件
from database.optimized_data_query import OptimizedStockDataQuery
from backtest.optimized_backtest_engine import OptimizedBacktestEngine
from strategies.strategy_factory import StrategyFactory


# ----------------- 工具函数 ----------------- #

def build_param_space(
    api: BacktestVisualizationAPI,
    strategy_id: str,
    whitelist_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    从 VisualizationAPI 拿到参数定义，并可选过滤一部分要优化的 key
    返回的每一项结构大致是：
    {
        "key": "volume_ratio_threshold",
        "label": "...",
        "type": "float"/"int",
        "min": 1.0,
        "max": 5.0,
        "default": 2.0,
        "description": "..."
    }
    """
    all_params = api.get_strategy_params(strategy_id)

    if whitelist_keys:
        all_params = [p for p in all_params if p["key"] in whitelist_keys]

    if not all_params:
        raise RuntimeError(f"策略 {strategy_id} 没有可用的参数元数据，请检查 VisualizationAPI.get_strategy_params")

    return all_params


def run_ga_optimization(
    strategy_id: str,
    start_date: str,
    end_date: str,
    pop_size: int = 50,
    generations: int = 10,
    keys: Optional[List[str]] = None,
    db_path: Optional[str] = None,
    n_workers: Optional[int] = None,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    给 Flask / 其他 Python 代码调用的 GA 入口（不走 argparse，不依赖命令行）。

    返回结构：
    {
        "best_score": float,
        "best_params": {...},
        "best_metrics": {...},
    }
    """
    import os
    # 设置环境变量防止重复预加载
    os.environ.setdefault("DISABLE_PRELOAD", "1")

    # 1) 用 VisualizationAPI 拿参数空间
    viz_api = BacktestVisualizationAPI(db_path=db_path)
    param_space = build_param_space(viz_api, strategy_id, whitelist_keys=keys)

    # 2) 创建数据查询实例并预加载数据
    data_query = OptimizedStockDataQuery(db_path=db_path, warmup=True)
    
    logger.info(f"开始预加载回测数据: {start_date} 到 {end_date}")
    t0 = time.time()
    data_query.preload_backtest_data(start_date, end_date)
    preload_cost = time.time() - t0
    logger.info("回测数据预加载完成")

    # 3) 创建优化回测引擎实例
    engine = OptimizedBacktestEngine(data_query)

    # 4) 跑 GA（使用多进程版本）
    t_ga = time.time()
    result = ga_optimize(
        engine=engine,
        param_space=param_space,
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        pop_size=pop_size,
        generations=generations,
        workers=4,  # 使用4个进程进行并行优化
        db_path=db_path,
    )
    ga_cost = time.time() - t_ga

    # 可以顺便把耗时一起返回，前端顺便展示
    result["timing"] = {
        "preload_seconds": round(preload_cost, 2),
        "ga_seconds": round(ga_cost, 2),
        "total_seconds": round(preload_cost + ga_cost, 2),
    }
    result["meta"] = {
        "strategy_id": strategy_id,
        "start_date": start_date,
        "end_date": end_date,
        "pop_size": pop_size,
        "generations": generations,
    }

    return result


def clamp_and_cast(value: float, spec: Dict[str, Any]) -> Any:
    """把 GA 里的连续值裁剪到 [min, max] 并按类型转成 int/float"""
    v = max(spec["min"], min(spec["max"], value))
    if spec.get("type", "float") == "int":
        return int(round(v))
    return float(v)


def param_vector_to_dict(
    vec: List[float],
    param_space: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """把 GA 中的向量 -> 参数字典 {key: value}"""
    params: Dict[str, Any] = {}
    for v, spec in zip(vec, param_space):
        params[spec["key"]] = clamp_and_cast(v, spec)
    return params


# ----------------- 回测评估函数 ----------------- #

def run_single_backtest(
    engine: OptimizedBacktestEngine,
    strategy_id: str,
    start_date: str,
    end_date: str,
    param_space: List[Dict[str, Any]],
    vec: List[float],
) -> Tuple[float, Dict[str, Any]]:
    """
    用一组参数跑一次回测，返回：
    - score: 用于 GA 的打分（这里用 totalReturn）
    - detail: { "metrics": {...}, "params": {...} }
    """
    # 向量 -> 参数字典
    params = param_vector_to_dict(vec, param_space)

    # 创建策略实例，并把参数塞进 dataclass config
    strategy = StrategyFactory.create_strategy(strategy_id, use_simple=True)
    if hasattr(strategy, "config"):
        cfg = strategy.config
        for k, v in params.items():
            if hasattr(cfg, k):
                # 冻结 dataclass 不能用 setattr，只能用 object.__setattr__ 暴力改
                object.__setattr__(cfg, k, v)

    final_metrics: Optional[Dict[str, Any]] = None

    # 用 engine 的流式接口跑回测，只关心 final_metrics
    for update in engine.run_backtest_streaming(start_date, end_date, strategy):
        if update.get("type") == "final_metrics":
            final_metrics = update.get("data") or {}

    if not final_metrics:
        # 没有结果：给一个很差的分数（惩罚）
        return -1e12, {"metrics": {}, "params": params}

    # 你也可以换成 annualizedReturn / sharpeRatio 等
    score = float(final_metrics.get("totalReturn", 0.0))

    return score, {"metrics": final_metrics, "params": params}


# ----------------- GA 主逻辑（个体操作） ----------------- #

def create_individual(param_space: List[Dict[str, Any]]) -> List[float]:
    """随机生成一个个体（参数向量）"""
    vec: List[float] = []
    for spec in param_space:
        v = random.uniform(spec["min"], spec["max"])
        vec.append(v)
    return vec


def mutate_individual(
    vec: List[float],
    param_space: List[Dict[str, Any]],
    mutation_rate: float = 0.2,
    mutation_strength: float = 0.1,
) -> None:
    """
    对个体做一点扰动：
    - mutation_rate：每个基因有多大概率被扰动
    - mutation_strength：扰动幅度，大约是范围的 10%
    """
    for i, spec in enumerate(param_space):
        if random.random() < mutation_rate:
            span = spec["max"] - spec["min"]
            noise = random.uniform(-span * mutation_strength, span * mutation_strength)
            vec[i] = max(spec["min"], min(spec["max"], vec[i] + noise))


def crossover(
    parent1: List[float],
    parent2: List[float],
) -> Tuple[List[float], List[float]]:
    """简单的一点交叉：在一个随机切点把父母拼起来"""
    if len(parent1) != len(parent2) or len(parent1) <= 1:
        return parent1[:], parent2[:]

    point = random.randint(1, len(parent1) - 1)
    child1 = parent1[:point] + parent2[point:]
    child2 = parent2[:point] + parent1[point:]
    return child1, child2


def tournament_select(
    scored_pop: List[Tuple[float, List[float]]],
    k: int = 3,
) -> List[float]:
    """锦标赛选择，从当前种群里抽 k 个，选最好一个。
    如果当前种群数量少于 k，则自动把 k 压缩到 len(scored_pop)。
    """
    if not scored_pop:
        raise ValueError("tournament_select: 空种群，无法选择个体")

    # 防止 k 大于当前种群数量
    k = max(1, min(k, len(scored_pop)))

    import random as _random
    competitors = _random.sample(scored_pop, k)
    competitors.sort(key=lambda x: x[0], reverse=True)
    return competitors[0][1][:]


# ----------------- 多进程全局变量 & worker 函数 ----------------- #

# 注意：这些变量只在各个子进程内部用（ProcessPoolExecutor initializer 会初始化）
_WORKER_ENGINE: Optional[OptimizedBacktestEngine] = None
_WORKER_STRATEGY_ID: Optional[str] = None
_WORKER_START: Optional[str] = None
_WORKER_END: Optional[str] = None
_WORKER_PARAM_SPACE: Optional[List[Dict[str, Any]]] = None


def _init_worker(
    db_path: Optional[str],
    strategy_id: str,
    start_date: str,
    end_date: str,
    param_space: List[Dict[str, Any]],
) -> None:
    """
    每个子进程启动时执行一次：
    - 创建自己的 OptimizedStockDataQuery + Engine
    - 在子进程内预加载一次数据
    """
    global _WORKER_ENGINE, _WORKER_STRATEGY_ID, _WORKER_START, _WORKER_END, _WORKER_PARAM_SPACE

    _WORKER_STRATEGY_ID = strategy_id
    _WORKER_START = start_date
    _WORKER_END = end_date
    _WORKER_PARAM_SPACE = param_space

    # 子进程里各自创建自己的 data_query 和 engine
    dq = OptimizedStockDataQuery(db_path=db_path)
    print(f"[WORKER {os.getpid()}] 开始预加载 {start_date} ~ {end_date} 的回测数据 ...")
    t0 = time.time()
    dq.preload_backtest_data(start_date, end_date)
    print(f"[WORKER {os.getpid()}] 预加载完成，用时 {time.time() - t0:.1f}s")

    _WORKER_ENGINE = OptimizedBacktestEngine(dq)


def _worker_eval_vec(vec: List[float]) -> Tuple[float, Dict[str, Any]]:
    """子进程中真正执行回测的函数"""
    global _WORKER_ENGINE, _WORKER_STRATEGY_ID, _WORKER_START, _WORKER_END, _WORKER_PARAM_SPACE

    if (
        _WORKER_ENGINE is None
        or _WORKER_STRATEGY_ID is None
        or _WORKER_START is None
        or _WORKER_END is None
        or _WORKER_PARAM_SPACE is None
    ):
        raise RuntimeError("Worker 未正确初始化，请检查 _init_worker 调用")

    try:
        return run_single_backtest(
            _WORKER_ENGINE,
            _WORKER_STRATEGY_ID,
            _WORKER_START,
            _WORKER_END,
            _WORKER_PARAM_SPACE,
            vec,
        )
    except Exception as e:
        # 出错时给一个很低的分数，避免整个 GA 崩掉
        print(f"[WORKER {os.getpid()}] 回测异常: {e}")
        params = param_vector_to_dict(vec, _WORKER_PARAM_SPACE)
        return -1e12, {"metrics": {}, "params": params}


# ----------------- GA 主逻辑 ----------------- #

def ga_optimize(
    engine: Optional[OptimizedBacktestEngine],
    param_space: List[Dict[str, Any]],
    strategy_id: str,
    start_date: str,
    end_date: str,
    pop_size: int = 20,
    generations: int = 20,
    workers: int = 1,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GA 主循环：返回 {best_score, best_params, best_metrics}

    - workers = 1: 单进程串行评估，使用传入的 engine（已预加载）。
    - workers > 1: 使用 ProcessPoolExecutor，多进程并行评估，每个子进程有自己的 engine。
    """
    # 简单缓存：相同参数不重复回测（在主进程里缓存结果）
    cache: Dict[Tuple[Tuple[str, Any], ...], Tuple[float, Dict[str, Any]]] = {}

    def eval_vec_sequential(vec: List[float]) -> Tuple[float, Dict[str, Any]]:
        """单进程模式下的评估函数"""
        params = param_vector_to_dict(vec, param_space)
        key = tuple(sorted(params.items()))
        if key in cache:
            return cache[key]
        if engine is None:
            raise RuntimeError("单进程模式需要有效的 engine")
        score, detail = run_single_backtest(
            engine,
            strategy_id,
            start_date,
            end_date,
            param_space,
            vec,
        )
        cache[key] = (score, detail)
        return score, detail

    # 初始化种群
    population: List[List[float]] = [create_individual(param_space) for _ in range(pop_size)]

    best_score = float("-inf")
    best_detail: Dict[str, Any] = {}

    if workers <= 1:
        # ---------------- 单进程版本 ----------------
        for gen in range(generations):
            gen_start = time.time()
            scored_pop: List[Tuple[float, List[float]]] = []

            # 评估当前种群
            for idx, vec in enumerate(population):
                score, detail = eval_vec_sequential(vec)
                scored_pop.append((score, vec))

                if score > best_score:
                    best_score = score
                    best_detail = detail

            # 按分数排序（从大到小）
            scored_pop.sort(key=lambda x: x[0], reverse=True)

            # 输出一眼进度
            top_score = scored_pop[0][0]
            print(
                f"[GEN {gen+1}/{generations}] "
                f"best_in_gen={top_score:.2f}, global_best={best_score:.2f}, "
                f"elapsed={time.time()-gen_start:.1f}s"
            )

            # 精英保留：保留前 20%
            elite_count = max(1, min(len(scored_pop), int(pop_size * 0.2)))
            new_population: List[List[float]] = [vec for _, vec in scored_pop[:elite_count]]

            # 不断繁衍直到凑够种群
            while len(new_population) < pop_size:
                parent1 = tournament_select(scored_pop, k=3)
                parent2 = tournament_select(scored_pop, k=3)
                child1, child2 = crossover(parent1, parent2)
                mutate_individual(child1, param_space)
                mutate_individual(child2, param_space)
                new_population.append(child1)
                if len(new_population) < pop_size:
                    new_population.append(child2)

            population = new_population

    else:
        # ---------------- 多进程版本 ----------------
        print(f"[INFO] 使用多进程 GA，workers={workers}（每个子进程会各自预加载一次数据）")
        # 创建进程池，initializer 里会为每个进程创建自己的 engine + 预加载
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(db_path, strategy_id, start_date, end_date, param_space),
        ) as executor:
            for gen in range(generations):
                gen_start = time.time()
                scored_pop: List[Tuple[float, List[float]]] = []

                # 先看哪些个体已经在 cache 里，哪些需要下发到子进程
                pending_indices: List[int] = []
                pending_vecs: List[List[float]] = []

                # 先尝试从缓存中取
                for idx, vec in enumerate(population):
                    params = param_vector_to_dict(vec, param_space)
                    key = tuple(sorted(params.items()))
                    if key in cache:
                        score, detail = cache[key]
                        scored_pop.append((score, vec))
                        if score > best_score:
                            best_score = score
                            best_detail = detail
                    else:
                        pending_indices.append(idx)
                        pending_vecs.append(vec)

                # 对未命中缓存的个体并行评估
                if pending_vecs:
                    futures = list(executor.map(_worker_eval_vec, pending_vecs))
                    for vec, (score, detail) in zip(pending_vecs, futures):
                        params = param_vector_to_dict(vec, param_space)
                        key = tuple(sorted(params.items()))
                        cache[key] = (score, detail)
                        scored_pop.append((score, vec))

                        if score > best_score:
                            best_score = score
                            best_detail = detail

                # 确保和种群一一对应
                if len(scored_pop) != len(population):
                    print(f"[WARN] scored_pop 长度 {len(scored_pop)} 与 population {len(population)} 不一致")

                # 按分数排序（从大到小）
                scored_pop.sort(key=lambda x: x[0], reverse=True)

                # 输出一眼进度
                top_score = scored_pop[0][0]
                print(
                    f"[GEN {gen+1}/{generations}] "
                    f"best_in_gen={top_score:.2f}, global_best={best_score:.2f}, "
                    f"elapsed={time.time()-gen_start:.1f}s"
                )

                # 精英保留：保留前 20%
                elite_count = max(1, min(len(scored_pop), int(pop_size * 0.2)))
                new_population: List[List[float]] = [vec for _, vec in scored_pop[:elite_count]]

                # 不断繁衍直到凑够种群
                while len(new_population) < pop_size:
                    parent1 = tournament_select(scored_pop, k=3)
                    parent2 = tournament_select(scored_pop, k=3)
                    child1, child2 = crossover(parent1, parent2)
                    mutate_individual(child1, param_space)
                    mutate_individual(child2, param_space)
                    new_population.append(child1)
                    if len(new_population) < pop_size:
                        new_population.append(child2)

                population = new_population

    return {
        "best_score": best_score,
        "best_params": best_detail.get("params", {}),
        "best_metrics": best_detail.get("metrics", {}),
    }


# ----------------- main：解析命令行 & 预加载 ----------------- #

def main():
    parser = argparse.ArgumentParser(description="GA 优化量化策略参数（结合 VisualizationAPI）")

    parser.add_argument("--strategy", required=True, help="策略 ID，例如：聚宽量比市值策略V3_严格趋势")
    parser.add_argument("--start", required=True, help="回测开始日期，YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="回测结束日期，YYYY-MM-DD")
    parser.add_argument("--db-path", default=None, help="SQLite 数据库路径，不填默认用 Config.DB_PATH")
    parser.add_argument("--pop-size", type=int, default=20, help="GA 种群大小")
    parser.add_argument("--generations", type=int, default=20, help="GA 迭代代数")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="并行进程数，1 表示单进程；建议使用 CPU 核心数的一半或略少一点",
    )

    args = parser.parse_args()

    # 调用统一入口函数
    print(
        f"[INFO] 启动 GA 优化：strategy={args.strategy}, "
        f"range={args.start}~{args.end}, pop={args.pop_size}, gen={args.generations}, workers={args.workers}"
    )
    t_total = time.time()
    result = run_ga_optimization(
        strategy_id=args.strategy,
        start_date=args.start,
        end_date=args.end,
        pop_size=args.pop_size,
        generations=args.generations,
        workers=args.workers,
        db_path=args.db_path,
    )
    print(f"[INFO] GA 完成，总耗时 {time.time()-t_total:.1f}s")

    print("\n==================== 最优结果 ====================")
    print(f"最佳分数（totalReturn%）：{result['best_score']:.2f}")
    print("\n最优参数：")
    for k, v in result["best_params"].items():
        print(f"  {k}: {v}")

    print("\n对应回测指标：")
    for k, v in result["best_metrics"].items():
        print(f"  {k}: {v}")

    print("==================================================")


if __name__ == "__main__":
    # Windows 下一定要这样包一层，避免多进程/子进程问题
    main()
