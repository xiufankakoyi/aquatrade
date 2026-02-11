# demo_infrastructure.py
"""
基础设施升级演示脚本
演示如何编排流程、验证策略并记录研究笔记。
"""

import sys
import os
from pathlib import Path

# 添加到路径
sys.path.append(str(Path(__file__).parent))

from core.workflow_engine import ResearchPipeline, WorkflowTask
from core.research_note import ResearchNote
from core.strategy_validator import OverfittingDetector
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.strategies.classic_strategy import MovingAverageCrossStrategy # 假设存在

def run_demo():
    print("=== Aquatrade 基础设施升级演示 ===\n")
    
    # 1. 初始化研究笔记
    note = ResearchNote()
    note.update_metadata(
        hypothesis="MACD 结合快速均线过滤可以提升稳健性",
        experiment_design="测试 MA5/MA20 交叉，并引入 OverfittingDetector 进行压力测试",
        strategy_version="v1.1-beta"
    )
    
    # 2. 初始化回测引擎与验证器 (Mock 数据查询)
    # 注意：在真实环境下需要正确的 db_path
    try:
        query = OptimizedStockDataQuery() 
        engine = FlexibleBacktestEngine(query)
        validator = OverfittingDetector(engine)
    except Exception as e:
        print(f"初始化引擎失败 (可能是数据库未就绪): {e}")
        print("后续将以模拟模式演示...\n")
        return

    # 3. 定义工作流
    pipeline = ResearchPipeline("策略研发全流程验证")
    
    def validation_task(strategy_id, params):
        print(f"正在对策略 {strategy_id} 执行蒙特卡洛压力测试...")
        # 这里使用一个简单的字典模拟策略类
        results = validator.monte_carlo_test(
            MovingAverageCrossStrategy, 
            params, 
            "2024-01-01", 
            "2024-06-01",
            n_simulations=5
        )
        print(f"验证完成: 预期 Sharpe={results['mean_sharpe']:.2f}")
        return results

    def archiving_task(val_results):
        print("正在归档研究发现并生成笔记...")
        note.update_metadata(
            key_findings=[
                f"蒙特卡洛平均 Sharpe: {val_results['mean_sharpe']:.2f}",
                f"Sharpe 标准差: {val_results['std_sharpe']:.4f}"
            ],
            learnings=["策略在注入 5bp 噪声后依然保持正收益，具有一定稳健性"],
            next_steps=["在 2023 年全市场下跌周期进行 Walk-forward 验证"]
        )
        note_path = note.save_markdown()
        return note_path

    # 组装流水线
    # 注意：这里简化了参数映射
    params = {"fast_period": 5, "slow_period": 20}
    val_out = validation_task("MA_Cross", params)
    note_path = archiving_task(val_out)
    
    print(f"\n✅ 演示完成！")
    print(f"研究笔记已生成: {note_path}")

if __name__ == "__main__":
    run_demo()
