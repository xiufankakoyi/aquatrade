# core/strategy_validator.py
"""
策略验证框架
包含过拟合检测、样本内外测试、多周期验证、蒙特卡洛测试等。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from config.logger import get_logger

logger = get_logger(__name__)

class OverfittingDetector:
    """
    过拟合检测与稳健性测试套件
    """
    
    def __init__(self, engine: FlexibleBacktestEngine):
        self.engine = engine

    def permutation_test(self, strategy_class, params: Dict, start_date: str, end_date: str, n_permutations: int = 10) -> Dict[str, Any]:
        """
        特征随机排列测试
        通过随机打乱输入数据的顺序（如果策略支持），观察性能变化。
        注意：这通常需要策略能够处理打乱后的数据，或者在回测引擎层面模拟。
        这里我们实现一个简化的版本：在回测过程中对返回的数据向量进行微小扰动。
        """
        logger.info(f"开始排列测试 (n={n_permutations})...")
        # 实际实现中，简单的排列测试可能需要对 data_query 进行 mock 或包装
        # 这里的示例逻辑是模拟运行并评估结果分布
        results = []
        for i in range(n_permutations):
            # 这里的逻辑应根据实际数据结构定制
            # 示例：运行一次标准回测作为基准
            try:
                # 这种测试在量化中通常是通过打乱收益率序列（Monte Carlo）或打乱特征-收益关联来实现
                pass # 实际代码量较大，此处先预留接口
            except Exception as e:
                logger.error(f"排列测试第 {i} 次迭代失败: {e}")
        
        return {"status": "implemented_skeleton", "message": "Permutation test needs specific data pipeline hooks."}

    def walk_forward_test(self, strategy_class, params: Dict, start_date: str, end_date: str, n_windows: int = 5, train_ratio: float = 0.7) -> List[Dict[str, Any]]:
        """
        滚动窗口步进测试 (Walk-Forward Analysis)
        将时间范围划分为多个 OOS (Out-of-Sample) 窗口。
        """
        logger.info(f"开始步进回测 (n_windows={n_windows})...")
        
        # 转换日期
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        total_days = (end_ts - start_ts).days
        
        window_size = total_days // n_windows
        results = []
        
        for i in range(n_windows):
            w_start = start_ts + timedelta(days=i * window_size)
            w_end = w_start + timedelta(days=window_size)
            if w_end > end_ts: w_end = end_ts
            
            w_start_str = w_start.strftime("%Y-%m-%d")
            w_end_str = w_end.strftime("%Y-%m-%d")
            
            logger.info(f"窗口 {i+1}: {w_start_str} -> {w_end_str}")
            
            # 创建策略实例
            strategy = strategy_class(**params)
            
            # 运行回测
            metrics = None
            try:
                stream = self.engine.run_backtest_streaming(w_start_str, w_end_str, strategy)
                for event in stream:
                    if event['type'] == 'final_metrics':
                        metrics = event['data']
                        break
                
                results.append({
                    "window": i + 1,
                    "start_date": w_start_str,
                    "end_date": w_end_str,
                    "metrics": metrics
                })
            except Exception as e:
                logger.error(f"窗口 {i+1} 回测失败: {e}")
                
        return results

    def monte_carlo_test(self, strategy_class, params: Dict, start_date: str, end_date: str, n_simulations: int = 20) -> Dict[str, Any]:
        """
        蒙特卡洛压力测试
        通过在执行价格中加入随机噪声（模拟滑点不确定性）或随机跳过交易。
        """
        logger.info(f"开始蒙特卡洛测试 (n={n_simulations})...")
        
        original_slippage = getattr(self.engine, 'slippage', 0.0)
        
        sim_results = []
        for i in range(n_simulations):
            # 注入随机扰动：随机调整手续费或滑点
            noise = np.random.normal(0, 0.0005) # 5个基点的噪声
            self.engine.commission_rate += noise
            
            strategy = strategy_class(**params)
            metrics = None
            try:
                stream = self.engine.run_backtest_streaming(start_date, end_date, strategy)
                for event in stream:
                    if event['type'] == 'final_metrics':
                        metrics = event['data']
                        break
                sim_results.append(metrics.get('sharpeRatio', 0) if metrics else 0)
            finally:
                # 还原
                self.engine.commission_rate -= noise
                
        return {
            "mean_sharpe": float(np.mean(sim_results)),
            "std_sharpe": float(np.std(sim_results)),
            "min_sharpe": float(np.min(sim_results)),
            "max_sharpe": float(np.max(sim_results)),
            "simulations": sim_results
        }
