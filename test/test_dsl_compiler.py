"""
strategies/dsl/compiler.py DSL 编译器测试

测试内容：
1. 策略编译
2. 信号编译
3. 过滤器编译
4. 缓存机制
5. 错误处理
"""

import pytest
import numpy as np


class TestDSLCompiler:
    """DSL 编译器测试"""
    
    @pytest.fixture
    def compiler(self):
        """创建编译器实例"""
        from core.strategies.dsl.compiler import DSLCompiler
        return DSLCompiler(engine="polars")
    
    @pytest.fixture
    def sample_strategy(self):
        """样本策略配置"""
        return {
            "version": "1.0",
            "metadata": {
                "id": "test_strategy",
                "name": "Test Strategy",
                "description": "A test strategy"
            },
            "signals": {
                "buy": {
                    "type": "crossover",
                    "fast": {"type": "ma", "window": 5},
                    "slow": {"type": "ma", "window": 20}
                }
            },
            "filters": [],
            "risk": []
        }
    
    def test_compiler_creation(self, compiler):
        """测试编译器创建"""
        assert compiler is not None
        assert compiler.engine == "polars"
    
    def test_compile_strategy(self, compiler, sample_strategy):
        """测试策略编译"""
        compiled = compiler.compile(sample_strategy)
        
        assert compiled is not None
        assert compiled.strategy_id == "test_strategy"
        assert compiled.strategy_name == "Test Strategy"
    
    def test_compile_strategy_cache(self, compiler, sample_strategy):
        """测试策略编译缓存"""
        compiled1 = compiler.compile(sample_strategy)
        compiled2 = compiler.compile(sample_strategy)
        
        assert compiled1.strategy_id == compiled2.strategy_id
    
    def test_get_cache_stats(self, compiler, sample_strategy):
        """测试缓存统计"""
        compiler.compile(sample_strategy)
        
        stats = compiler.get_cache_stats()
        
        assert stats["cache_size"] >= 1
        assert len(stats["cached_ids"]) >= 1
    
    def test_clear_cache(self, compiler, sample_strategy):
        """测试清空缓存"""
        compiler.compile(sample_strategy)
        compiler.clear_cache()
        
        stats = compiler.get_cache_stats()
        
        assert stats["cache_size"] == 0


class TestCompiledStrategy:
    """编译后策略测试"""
    
    @pytest.fixture
    def compiled_strategy(self):
        """创建编译后策略"""
        from core.strategies.dsl.compiler import DSLCompiler
        
        strategy = {
            "version": "1.0",
            "metadata": {
                "id": "test",
                "name": "Test"
            },
            "signals": {
                "buy": {
                    "type": "crossover",
                    "fast": {"type": "ma", "window": 5},
                    "slow": {"type": "ma", "window": 20}
                }
            },
            "filters": [],
            "risk": []
        }
        
        compiler = DSLCompiler(engine="polars")
        return compiler.compile(strategy)
    
    def test_compiled_strategy_attributes(self, compiled_strategy):
        """测试编译后策略属性"""
        assert hasattr(compiled_strategy, 'strategy_id')
        assert hasattr(compiled_strategy, 'strategy_name')
        assert hasattr(compiled_strategy, 'signal_exprs')
        assert hasattr(compiled_strategy, 'filter_exprs')
    
    def test_compiled_strategy_required_columns(self, compiled_strategy):
        """测试依赖列提取"""
        assert isinstance(compiled_strategy.required_columns, list)
    
    def test_compiled_strategy_raw_config(self, compiled_strategy):
        """测试原始配置"""
        assert isinstance(compiled_strategy.raw_config, dict)
        assert compiled_strategy.raw_config.get("version") == "1.0"


class TestOptimizingCompiler:
    """优化编译器测试"""
    
    @pytest.fixture
    def optimizer(self):
        """创建优化编译器"""
        from core.strategies.dsl.compiler import OptimizingCompiler
        return OptimizingCompiler(engine="polars")
    
    def test_optimizer_creation(self, optimizer):
        """测试优化编译器创建"""
        assert optimizer is not None
    
    def test_compile_strategy(self, optimizer):
        """测试优化编译器编译策略"""
        strategy = {
            "version": "1.0",
            "metadata": {
                "id": "test",
                "name": "Test"
            },
            "signals": {
                "buy": {
                    "type": "crossover",
                    "fast": {"type": "ma", "window": 5},
                    "slow": {"type": "ma", "window": 20}
                }
            },
            "filters": [],
            "risk": []
        }
        
        compiled = optimizer.compile(strategy)
        
        assert compiled is not None


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_compile_strategy_function(self):
        """测试 compile_strategy 便捷函数"""
        from core.strategies.dsl.compiler import compile_strategy
        
        strategy = {
            "version": "1.0",
            "metadata": {"id": "test", "name": "Test"},
            "signals": {
                "buy": {
                    "type": "crossover",
                    "fast": {"type": "ma", "window": 5},
                    "slow": {"type": "ma", "window": 20}
                }
            },
            "filters": [],
            "risk": []
        }
        
        compiled = compile_strategy(strategy)
        
        assert compiled is not None


class TestDSLErrorHandling:
    """DSL 错误处理测试"""
    
    def test_invalid_strategy_missing_metadata(self):
        """测试缺少元数据的策略"""
        from core.strategies.dsl.compiler import DSLCompiler
        
        compiler = DSLCompiler()
        
        strategy = {
            "version": "1.0",
            "signals": {},
            "filters": [],
            "risk": []
        }
        
        with pytest.raises(ValueError):
            compiler.compile(strategy)
    
    def test_invalid_engine(self):
        """测试无效引擎"""
        from core.strategies.dsl.compiler import DSLCompiler
        
        with pytest.raises(ValueError):
            DSLCompiler(engine="invalid")
