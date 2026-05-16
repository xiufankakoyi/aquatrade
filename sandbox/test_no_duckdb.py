"""
测试验证：确保项目中没有使用 DuckDB，所有功能都使用 Polars
"""
import sys
import os
import ast
from pathlib import Path
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestNoDuckDBImports:
    """测试确保没有 DuckDB 导入"""
    
    def test_no_duckdb_import_in_core(self):
        """测试 core 目录没有 duckdb 导入"""
        core_dir = project_root / "core"
        duckdb_files = self._find_duckdb_imports(core_dir)
        assert len(duckdb_files) == 0, f"发现 DuckDB 导入: {duckdb_files}"
    
    def test_no_duckdb_import_in_data_svc(self):
        """测试 data_svc 目录没有 duckdb 导入"""
        data_svc_dir = project_root / "data_svc"
        duckdb_files = self._find_duckdb_imports(data_svc_dir)
        assert len(duckdb_files) == 0, f"发现 DuckDB 导入: {duckdb_files}"
    
    def test_no_duckdb_import_in_server(self):
        """测试 server 目录没有 duckdb 导入"""
        server_dir = project_root / "server"
        duckdb_files = self._find_duckdb_imports(server_dir)
        assert len(duckdb_files) == 0, f"发现 DuckDB 导入: {duckdb_files}"
    
    def test_no_duckdb_import_in_config(self):
        """测试 config 目录没有 duckdb 导入"""
        config_dir = project_root / "config"
        duckdb_files = self._find_duckdb_imports(config_dir)
        assert len(duckdb_files) == 0, f"发现 DuckDB 导入: {duckdb_files}"
    
    def _find_duckdb_imports(self, directory: Path) -> list:
        """查找目录中的 DuckDB 导入"""
        duckdb_files = []
        if not directory.exists():
            return duckdb_files
        
        for py_file in directory.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 检查是否有 duckdb 导入
                if 'import duckdb' in content or 'from duckdb' in content:
                    rel_path = py_file.relative_to(project_root)
                    duckdb_files.append(str(rel_path))
            except Exception:
                continue
        
        return duckdb_files


class TestPolarsAnalyticsExists:
    """测试 PolarsAnalytics 模块存在且功能正常"""
    
    def test_polars_analytics_module_exists(self):
        """测试 PolarsAnalytics 模块存在"""
        try:
            from data_svc.analytics.polars_analytics import PolarsAnalytics
            assert True
        except ImportError as e:
            pytest.fail(f"无法导入 PolarsAnalytics: {e}")
    
    def test_polars_analytics_has_required_methods(self):
        """测试 PolarsAnalytics 有必需的方法"""
        from data_svc.analytics.polars_analytics import PolarsAnalytics
        
        required_methods = [
            'from_arrow',
            'from_pandas',
            'to_pandas',
            'calculate_ma',
            'calculate_rsi',
            'calculate_macd',
            'cross_sectional_rank',
            'query_from_arrow',
        ]
        
        for method in required_methods:
            assert hasattr(PolarsAnalytics, method), f"缺少方法: {method}"
    
    def test_polars_analytics_uses_polars(self):
        """测试 PolarsAnalytics 实际使用 Polars"""
        import polars as pl
        from data_svc.analytics.polars_analytics import PolarsAnalytics
        
        analytics = PolarsAnalytics()
        
        # 创建测试数据
        test_data = pl.DataFrame({
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close': [100.0, 101.0, 102.0],
        })
        
        # 测试计算 MA (使用 windows 参数)
        result = analytics.calculate_ma(test_data, windows=[2])
        assert result is not None
        assert 'ma2' in result.columns


class TestUnifiedRepositoryUsesPolars:
    """测试 UnifiedRepository 使用 Polars"""
    
    def test_unified_repository_imports(self):
        """测试 UnifiedRepository 导入的是 PolarsAnalytics 而不是 DuckAnalyzer"""
        try:
            from data_svc.store.unified_repository import UnifiedRepository
            import inspect
            source = inspect.getsource(UnifiedRepository)
            
            # 确保导入的是 PolarsAnalytics
            assert 'PolarsAnalytics' in source, "应该导入 PolarsAnalytics"
            assert 'DuckAnalyzer' not in source, "不应该导入 DuckAnalyzer"
        except ImportError as e:
            pytest.fail(f"无法导入 UnifiedRepository: {e}")
    
    def test_unified_repository_has_analyzer(self):
        """测试 UnifiedRepository 有 analyzer 属性"""
        try:
            from data_svc.store.unified_repository import UnifiedRepository
            # 检查类定义中有 analyzer 属性
            import inspect
            source = inspect.getsource(UnifiedRepository)
            assert 'self.analyzer' in source or 'analyzer' in source
        except ImportError as e:
            pytest.fail(f"无法检查 UnifiedRepository: {e}")


class TestNoDuckDBDependency:
    """测试没有 DuckDB 依赖"""
    
    def test_requirements_txt_no_duckdb(self):
        """测试 requirements.txt 没有 duckdb"""
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            with open(req_file, 'r') as f:
                content = f.read().lower()
            assert 'duckdb' not in content, "requirements.txt 中不应该有 duckdb"
    
    def test_can_import_without_duckdb(self):
        """测试可以在没有 duckdb 的情况下导入核心模块"""
        # 确保 duckdb 不在 sys.modules 中
        if 'duckdb' in sys.modules:
            del sys.modules['duckdb']
        
        # 尝试导入核心模块
        try:
            from data_svc.analytics import PolarsAnalytics
            from data_svc.store import UnifiedRepository
            assert True
        except ImportError as e:
            if 'duckdb' in str(e).lower():
                pytest.fail(f"导入依赖 duckdb: {e}")


class TestDataQueryUsesPolars:
    """测试数据查询使用 Polars"""
    
    def test_optimized_data_query_uses_polars(self):
        """测试 OptimizedStockDataQuery 使用 Polars"""
        try:
            from data_svc.database.optimized_data_query import OptimizedStockDataQuery
            import inspect
            source = inspect.getsource(OptimizedStockDataQuery)
            
            # 确保使用 Polars
            assert 'import polars' in source or 'polars as pl' in source
            
            # 确保不使用 DuckDB
            assert 'import duckdb' not in source
        except ImportError as e:
            pytest.fail(f"无法检查 OptimizedStockDataQuery: {e}")


class TestSpiderAppUsesPolars:
    """测试 spider app 使用 Polars"""
    
    def test_spider_app_uses_polars(self):
        """测试 spider/app.py 使用 Polars 而不是 DuckDB"""
        spider_app = project_root / "data_svc" / "spider" / "app.py"
        if spider_app.exists():
            with open(spider_app, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 确保使用 Polars
            assert 'import polars' in content or 'polars as pl' in content
            
            # 确保不使用 DuckDB
            assert 'import duckdb' not in content
            assert 'duckdb.connect' not in content


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
