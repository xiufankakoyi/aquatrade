"""
MACD四阴线策略 - 混合优化（遗传算法 + 贝叶斯优化）

使用遗传算法进行全局搜索，贝叶斯优化进行局部寻优
滚动窗口交叉验证 Calmar 比率
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
import json
import random
from typing import List, Dict, Tuple, Any
from copy import deepcopy

# 从 bayesian_optimization 导入所需函数
from sandbox.bayesian_optimization import (
    calc_ema, calc_macd, calc_rsi, calc_atr, calc_ma,
    calc_vol_ma, calc_std, detect_signal, calc_volatility_strength,
    load_data, run_backtest
)


def calc_calmar_ratio(total_return: float, max_drawdown: float, years: float) -> float:
    """Calmar = 年化收益 / |最大回撤|

    Args:
        total_return: 总收益率（百分比）
        max_drawdown: 最大回撤（百分比）
        years: 投资年数

    Returns:
        Calmar比率
    """
    annual_return = (1 + total_return / 100) ** (1 / years) - 1
    if max_drawdown == 0:
        return 0
    return annual_return / (max_drawdown / 100)


class GeneticOptimizer:
    """遗传算法优化器"""

    PARAM_SPACE = {
        'vs_threshold': (0.0, 1.5),
        'rsi_max': (30.0, 70.0),
        'ma_diff_threshold': (0.0, 0.1),
        'take_profit_pct': (0.01, 0.15),
        'stop_loss_pct': (0.01, 0.08),
        'trailing_stop_pct': (0.01, 0.08),
        'max_holding_days': (3, 15),
        'rsi_filter': [True, False],
        'ma_diff_filter': [True, False],
    }

    CONTINUOUS_PARAMS = ['vs_threshold', 'rsi_max', 'ma_diff_threshold',
                         'take_profit_pct', 'stop_loss_pct', 'trailing_stop_pct']
    INTEGER_PARAMS = ['max_holding_days']
    CATEGORICAL_PARAMS = ['rsi_filter', 'ma_diff_filter']

    def __init__(self, population_size: int = 100, n_generations: int = 20,
                 crossover_rate: float = 0.8, mutation_rate: float = 0.1,
                 elite_size: int = 10, random_seed: int = 42):
        """初始化遗传算法

        Args:
            population_size: 种群大小
            n_generations: 迭代代数
            crossover_rate: 交叉概率
            mutation_rate: 变异概率
            elite_size: 精英个体数量
            random_seed: 随机种子
        """
        self.population_size = population_size
        self.n_generations = n_generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        random.seed(random_seed)
        np.random.seed(random_seed)
        self.population: List[Dict] = []
        self.fitness_history: List[float] = []

    def _create_individual(self) -> Dict[str, Any]:
        """创建单个个体"""
        individual = {}
        for param, (low, high) in self.PARAM_SPACE.items():
            if param in self.CATEGORICAL_PARAMS:
                individual[param] = random.choice(param)
            elif param in self.INTEGER_PARAMS:
                individual[param] = random.randint(low, high)
            else:
                individual[param] = random.uniform(low, high)
        return individual

    def initialize_population(self) -> None:
        """初始化种群"""
        self.population = [self._create_individual() for _ in range(self.population_size)]

    def _evaluate_fitness(self, individual: Dict, daily_data) -> float:
        """评估个体适应度（使用滚动窗口 Calmar）"""
        return rolling_window_calmar(daily_data, individual)

    def _selection(self, fitnesses: List[float]) -> List[int]:
        """锦标赛选择"""
        tournament_size = 5
        selected = []
        for _ in range(len(self.population)):
            candidates = random.sample(range(len(self.population)), tournament_size)
            best = max(candidates, key=lambda i: fitnesses[i])
            selected.append(best)
        return selected

    def _crossover(self, parent1: Dict, parent2: Dict) -> Tuple[Dict, Dict]:
        """均匀交叉"""
        if random.random() > self.crossover_rate:
            return deepcopy(parent1), deepcopy(parent2)

        child1, child2 = {}, {}
        for param in self.PARAM_SPACE.keys():
            if random.random() < 0.5:
                child1[param] = parent1[param]
                child2[param] = parent2[param]
            else:
                child1[param] = parent2[param]
                child2[param] = parent1[param]
        return child1, child2

    def _mutate(self, individual: Dict) -> Dict:
        """高斯变异"""
        mutated = deepcopy(individual)
        for param in self.CONTINUOUS_PARAMS:
            if random.random() < self.mutation_rate:
                low, high = self.PARAM_SPACE[param]
                mutated[param] = np.clip(
                    individual[param] + np.random.normal(0, (high - low) * 0.1),
                    low, high
                )
        for param in self.INTEGER_PARAMS:
            if random.random() < self.mutation_rate:
                low, high = self.PARAM_SPACE[param]
                mutated[param] = int(np.clip(
                    individual[param] + int(np.random.normal(0, 2)),
                    low, high
                ))
        for param in self.CATEGORICAL_PARAMS:
            if random.random() < self.mutation_rate:
                mutated[param] = random.choice(self.PARAM_SPACE[param])
        return mutated

    def optimize(self, daily_data) -> List[Dict]:
        """运行遗传算法优化

        Args:
            daily_data: 行情数据

        Returns:
            Top 10 最优个体
        """
        print("=" * 60)
        print("遗传算法 - 全局搜索")
        print("=" * 60)
        print(f"种群大小: {self.population_size}, 迭代代数: {self.n_generations}")
        sys.stdout.flush()

        self.initialize_population()

        for generation in range(self.n_generations):
            fitnesses = []
            for ind in self.population:
                fitness = self._evaluate_fitness(ind, daily_data)
                fitnesses.append(fitness)

            best_fitness = max(fitnesses)
            avg_fitness = np.mean(fitnesses)
            self.fitness_history.append(best_fitness)

            if generation % 5 == 0 or generation == self.n_generations - 1:
                print(f"代 {generation:2d}: 最佳适应度={best_fitness:.4f}, 平均={avg_fitness:.4f}")
                sys.stdout.flush()

            selected_indices = self._selection(fitnesses)

            new_population = []
            elites = sorted(range(len(fitnesses)),
                          key=lambda i: fitnesses[i],
                          reverse=True)[:self.elite_size]
            for idx in elites:
                new_population.append(deepcopy(self.population[idx]))

            while len(new_population) < self.population_size:
                idx1, idx2 = random.sample(selected_indices, 2)
                child1, child2 = self._crossover(
                    self.population[idx1],
                    self.population[idx2]
                )
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)
                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)

            self.population = new_population

        final_fitnesses = []
        for ind in self.population:
            fitness = self._evaluate_fitness(ind, daily_data)
            final_fitnesses.append(fitness)

        sorted_indices = sorted(range(len(final_fitnesses)),
                                key=lambda i: final_fitnesses[i],
                                reverse=True)[:self.elite_size]

        top_individuals = [deepcopy(self.population[i]) for i in sorted_indices]
        top_individuals.sort(key=lambda x: rolling_window_calmar(daily_data, x), reverse=True)

        print(f"\n遗传算法完成! Top 10 个体适应度:")
        for i, ind in enumerate(top_individuals[:10]):
            fit = rolling_window_calmar(daily_data, ind)
            print(f"  {i+1}. Calmar={fit:.4f}")

        return top_individuals[:10]


def rolling_window_calmar(daily_data, config: Dict) -> float:
    """滚动窗口交叉验证目标函数

    Args:
        daily_data: 行情数据
        config: 参数配置

    Returns:
        平均 Calmar 比率（不足100笔交易返回-10）
    """
    # 简化：只用2024年单窗口评估（加快遗传算法速度）
    windows = [
        ("2024-01-01", "2024-12-31"),
    ]

    calmar_ratios = []

    for start_date, end_date in windows:
        config_copy = {
            'start_date': start_date,
            'end_date': end_date,
            'vs_threshold': config.get('vs_threshold', 0),
            'rsi_filter': config.get('rsi_filter', False),
            'rsi_max': config.get('rsi_max', 60),
            'ma_diff_filter': config.get('ma_diff_filter', False),
            'ma_diff_threshold': config.get('ma_diff_threshold', 0),
            'take_profit_pct': config.get('take_profit_pct', 0.03),
            'stop_loss_pct': config.get('stop_loss_pct', 0.02),
            'trailing_stop_pct': config.get('trailing_stop_pct', 0.02),
            'max_holding_days': config.get('max_holding_days', 10),
        }

        result = run_backtest(daily_data, config_copy)

        years = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days / 365
        min_trades_per_year = 100
        required_trades = int(min_trades_per_year * years)

        if result['trade_count'] < required_trades:
            return -10

        if result['max_drawdown'] == 0:
            continue

        calmar = calc_calmar_ratio(
            result['total_return'],
            result['max_drawdown'],
            years
        )
        calmar_ratios.append(calmar)

    if not calmar_ratios:
        return -10

    return np.mean(calmar_ratios)


def bayesian_optimize_from_seeds(seed_population: List[Dict], daily_data,
                                  n_trials: int = 50) -> Dict:
    """从种子区域运行贝叶斯优化

    Args:
        seed_population: 遗传算法得到的种子种群
        daily_data: 行情数据
        n_trials: 迭代次数

    Returns:
        最优参数
    """
    print("\n" + "=" * 60)
    print("贝叶斯优化 - 局部寻优")
    print("=" * 60)

    param_centers = {}
    for param in GeneticOptimizer.CONTINUOUS_PARAMS + GeneticOptimizer.INTEGER_PARAMS:
        values = [ind[param] for ind in seed_population if param in ind]
        if values:
            param_centers[param] = np.mean(values)

    param_stds = {}
    for param in GeneticOptimizer.CONTINUOUS_PARAMS + GeneticOptimizer.INTEGER_PARAMS:
        values = [ind[param] for ind in seed_population if param in ind]
        if values:
            param_stds[param] = max(np.std(values), 0.01)

    def objective(trial):
        config = {}
        for param, (low, high) in GeneticOptimizer.PARAM_SPACE.items():
            if param in GeneticOptimizer.CONTINUOUS_PARAMS:
                center = param_centers.get(param, (low + high) / 2)
                std = param_stds.get(param, (high - low) / 4)
                suggested = trial.suggest_float(param, low, high)
                config[param] = suggested
            elif param in GeneticOptimizer.INTEGER_PARAMS:
                config[param] = trial.suggest_int(param, int(low), int(high))
            elif param in GeneticOptimizer.CATEGORICAL_PARAMS:
                config[param] = trial.suggest_categorical(param, [True, False])

        return rolling_window_calmar(daily_data, config)

    study = optuna.create_study(
        direction='maximize',
        sampler=TPESampler(seed=42)
    )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    print(f"\n贝叶斯优化完成!")
    print(f"  最佳 Calmar: {study.best_value:.4f}")
    print(f"  最佳参数: {study.best_params}")

    return study.best_params


def main():
    """主函数 - 混合优化流程"""
    print("=" * 60)
    print("MACD四阴线策略 - 混合优化（遗传算法 + 贝叶斯优化）")
    print("=" * 60)

    train_start = "2024-01-01"
    train_end = "2025-12-31"

    print("\n加载数据...")
    daily_data = load_data(train_start, train_end)
    print(f"数据加载完成: {len(daily_data)} 只股票")

    # 小规模快速测试
    ga = GeneticOptimizer(
        population_size=30,  # 减少到30
        n_generations=5,    # 减少到5
        crossover_rate=0.8,
        mutation_rate=0.1,
        elite_size=5,
        random_seed=42
    )

    top_individuals = ga.optimize(daily_data)

    best_params = bayesian_optimize_from_seeds(top_individuals, daily_data, n_trials=50)

    print("\n" + "=" * 60)
    print("最终结果验证")
    print("=" * 60)

    test_windows = [
        ("2022-01-01", "2023-12-31", "2022-2023"),
        ("2023-01-01", "2024-12-31", "2023-2024"),
        ("2024-01-01", "2025-12-31", "2024-2025"),
    ]

    results = []
    for start, end, name in test_windows:
        config = {
            'start_date': start,
            'end_date': end,
            **best_params
        }
        result = run_backtest(daily_data, config)
        result['window'] = name
        results.append(result)

        years = (pd.to_datetime(end) - pd.to_datetime(start)).days / 365
        calmar = calc_calmar_ratio(
            result['total_return'],
            result['max_drawdown'],
            years
        )
        print(f"\n{name}:")
        print(f"  总收益: {result['total_return']:.2f}%")
        print(f"  最大回撤: {result['max_drawdown']:.2f}%")
        print(f"  Calmar: {calmar:.4f}")
        print(f"  交易次数: {result['trade_count']}")
        print(f"  胜率: {result['win_rate']:.1f}%")

    output_path = Path(__file__).parent / "hybrid_optimization_results.json"
    result_data = {
        'best_params': best_params,
        'window_results': results,
        'ga_fitness_history': ga.fitness_history,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
