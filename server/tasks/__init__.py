"""
Celery 任务包
============

包含所有异步任务定义：
- backtest_tasks: 回测相关任务
- optimization_tasks: 参数优化任务（待添加）
- data_tasks: 数据处理任务（待添加）
"""

# 导入所有任务模块，确保 Celery 能发现它们
from server.tasks import backtest_tasks

__all__ = ['backtest_tasks']
