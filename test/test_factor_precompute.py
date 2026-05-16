"""
core/strategies/utils/factor_precompute.py 因子预计算引擎测试

测试内容：
1. FactorNode 数据类
2. FactorDAG 依赖图
3. 常量和加速库检测
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestFactorNode:
    """因子节点测试"""
    
    def test_factor_node_init(self):
        """测试因子节点初始化"""
        from core.strategies.utils.factor_precompute import FactorNode
        
        node = FactorNode(
            name="test_factor",
            dependencies={"ma5", "ma10"},
            compute_func=lambda x: x,
            cache_key="test_key"
        )
        
        assert node.name == "test_factor"
        assert "ma5" in node.dependencies
        assert "ma10" in node.dependencies
        assert node.cache_key == "test_key"
    
    def test_factor_node_default_dependencies(self):
        """测试默认依赖为空集合"""
        from core.strategies.utils.factor_precompute import FactorNode
        
        node = FactorNode(name="test_factor")
        
        assert node.dependencies == set()


class TestFactorDAG:
    """因子依赖图测试"""
    
    def test_dag_init(self):
        """测试DAG初始化"""
        from core.strategies.utils.factor_precompute import FactorDAG
        
        dag = FactorDAG()
        
        assert dag.nodes == {}
    
    def test_dag_add_factor(self):
        """测试添加因子"""
        from core.strategies.utils.factor_precompute import FactorDAG
        
        dag = FactorDAG()
        
        def dummy_func(x):
            return x
        
        dag.add_factor(
            name="test_factor",
            dependencies=["ma5", "ma10"],
            compute_func=dummy_func
        )
        
        assert "test_factor" in dag.nodes
        assert dag.nodes["test_factor"].name == "test_factor"
    
    def test_dag_check_factor_in_nodes(self):
        """测试检查因子是否在nodes中"""
        from core.strategies.utils.factor_precompute import FactorDAG
        
        dag = FactorDAG()
        
        assert "test_factor" not in dag.nodes
        
        dag.add_factor(
            name="test_factor",
            dependencies=[],
            compute_func=lambda x: x
        )
        
        assert "test_factor" in dag.nodes


class TestFactorPrecomputeConstants:
    """因子预计算常量测试"""
    
    def test_bottleneck_available_constant(self):
        """测试 BOTTLENECK_AVAILABLE 常量"""
        from core.strategies.utils.factor_precompute import BOTTLENECK_AVAILABLE
        
        assert isinstance(BOTTLENECK_AVAILABLE, bool)
    
    def test_numba_available_constant(self):
        """测试 NUMBA_AVAILABLE 常量"""
        from core.strategies.utils.factor_precompute import NUMBA_AVAILABLE
        
        assert isinstance(NUMBA_AVAILABLE, bool)
