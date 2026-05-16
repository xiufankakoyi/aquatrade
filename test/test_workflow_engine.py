"""
core/workflow_engine.py 工作流引擎测试

测试内容：
1. WorkflowTask 任务类
2. ResearchPipeline 流水线类
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestWorkflowTask:
    """工作流任务测试"""
    
    def test_task_init(self):
        """测试任务初始化"""
        from core.workflow_engine import WorkflowTask
        
        def dummy_func():
            return "success"
        
        task = WorkflowTask("test_task", dummy_func, param1=1, param2=2)
        
        assert task.name == "test_task"
        assert task.status == "pending"
        assert task.kwargs == {"param1": 1, "param2": 2}
    
    def test_task_execute_success(self):
        """测试任务执行成功"""
        from core.workflow_engine import WorkflowTask
        
        def dummy_func(value):
            return value * 2
        
        task = WorkflowTask("test_task", dummy_func, value=5)
        result = task.execute()
        
        assert task.status == "success"
        assert result == 10
        assert task.start_time is not None
        assert task.end_time is not None
    
    def test_task_execute_failure(self):
        """测试任务执行失败"""
        from core.workflow_engine import WorkflowTask
        
        def failing_func():
            raise ValueError("Test error")
        
        task = WorkflowTask("test_task", failing_func)
        result = task.execute()
        
        assert task.status == "failed"
        assert task.error is not None


class TestResearchPipeline:
    """研究流水线测试"""
    
    def test_pipeline_init(self):
        """测试流水线初始化"""
        from core.workflow_engine import ResearchPipeline
        
        pipeline = ResearchPipeline("test_pipeline")
        
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.tasks) == 0
        assert pipeline.context == {}
    
    def test_pipeline_add_task(self):
        """测试添加任务"""
        from core.workflow_engine import ResearchPipeline
        
        def dummy_func():
            return "success"
        
        pipeline = ResearchPipeline("test_pipeline")
        pipeline.add_task("task1", dummy_func)
        
        assert len(pipeline.tasks) == 1
        assert pipeline.tasks[0].name == "task1"
    
    def test_pipeline_add_task_returns_self(self):
        """测试添加任务返回自身"""
        from core.workflow_engine import ResearchPipeline
        
        def dummy_func():
            return "success"
        
        pipeline = ResearchPipeline("test_pipeline")
        result = pipeline.add_task("task1", dummy_func)
        
        assert result is pipeline
