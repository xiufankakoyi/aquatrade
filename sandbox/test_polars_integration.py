"""
集成测试：验证所有模块真正使用 Polars 进行数据计算
"""
import sys
import os
from pathlib import Path
import pytest
import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestWatchlistManagerPolars:
    """测试 watchlist_manager 使用 Polars"""
    
    def test_load_watchlist_uses_polars(self):
        """测试加载自选股使用 Polars 读取 Parquet"""
        from core.portfolio.watchlist_manager import WatchlistManager
        import inspect
        
        source = inspect.getsource(WatchlistManager)
        # 确保使用 pl.read_parquet
        assert 'pl.read_parquet' in source or 'polars' in source
        # 确保不使用 duckdb
        assert 'duckdb.connect' not in source
        assert 'duckdb.sql' not in source


class TestPositionHistoryManagerPolars:
    """测试 position_history_manager 使用 Polars"""
    
    def test_load_history_uses_polars(self):
        """测试加载历史使用 Polars"""
        from core.portfolio.position_history_manager import PositionHistoryManager
        import inspect
        
        source = inspect.getsource(PositionHistoryManager)
        assert 'pl.read_parquet' in source or 'polars' in source
        assert 'duckdb.connect' not in source


class TestProfileRepositoryPolars:
    """测试 profile_repository 使用 ArcticDB + Polars"""
    
    def test_profile_uses_polars(self):
        """测试使用 Polars DataFrame"""
        from core.profiles import profile_repository
        import inspect
        
        source = inspect.getsource(profile_repository)
        assert 'pl.DataFrame' in source or 'polars' in source
        assert 'import polars' in source
        assert 'duckdb' not in source


class TestScreenerRoutesPolars:
    """测试 screener_routes 使用 Polars"""
    
    def test_screener_imports_polars(self):
        """测试导入 Polars"""
        source_file = project_root / "server" / "routes" / "screener_routes.py"
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'import polars as pl' in content
        assert 'duckdb' not in content


class TestSentimentRoutesPolars:
    """测试 sentiment_routes 使用 Polars"""
    
    def test_sentiment_uses_polars_scan(self):
        """测试使用 pl.scan_parquet"""
        source_file = project_root / "server" / "routes" / "sentiment_routes.py"
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'pl.scan_parquet' in content or 'pl.read_parquet' in content
        assert 'duckdb.connect' not in content
        assert 'duckdb.sql' not in content


class TestStockDataServicePolars:
    """测试 stock_data_service 使用 Polars"""
    
    def test_data_service_uses_polars(self):
        """测试数据服务使用 Polars"""
        from server.services import stock_data_service
        import inspect
        
        source = inspect.getsource(stock_data_service)
        assert 'polars' in source or 'pl.' in source
        assert 'duckdb' not in source


class TestGubaServicePolars:
    """测试 guba_service 使用 Polars"""
    
    def test_guba_uses_polars(self):
        """测试股吧服务使用 Polars"""
        from server.services import guba_service
        import inspect
        
        source = inspect.getsource(guba_service)
        assert 'polars' in source or 'pl.' in source
        assert 'duckdb' not in source


class TestUnifiedRepositoryPolars:
    """测试 unified_repository 使用 PolarsAnalytics"""
    
    def test_unified_repo_uses_polars_analytics(self):
        """测试使用 PolarsAnalytics"""
        from data_svc.store.unified_repository import UnifiedRepository
        import inspect
        
        source = inspect.getsource(UnifiedRepository)
        assert 'PolarsAnalytics' in source
        assert 'self.analyzer = PolarsAnalytics()' in source
        assert 'DuckAnalyzer' not in source
        assert 'duckdb' not in source


class TestPolarsAnalyticsFunctional:
    """测试 PolarsAnalytics 功能正常"""
    
    def test_calculate_ma_works(self):
        """测试计算 MA 真正工作"""
        from data_svc.analytics.polars_analytics import PolarsAnalytics
        
        analytics = PolarsAnalytics()
        
        # 创建测试数据
        df = pl.DataFrame({
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
            'close': [100.0, 101.0, 102.0, 103.0, 104.0],
        })
        
        result = analytics.calculate_ma(df, windows=[2])
        
        assert 'ma2' in result.columns
        # 验证计算正确
        ma2_values = result['ma2'].to_list()
        assert ma2_values[1] == 100.5  # (100+101)/2
        assert ma2_values[2] == 101.5  # (101+102)/2
    
    def test_calculate_rsi_works(self):
        """测试计算 RSI 真正工作"""
        from data_svc.analytics.polars_analytics import PolarsAnalytics
        
        analytics = PolarsAnalytics()
        
        df = pl.DataFrame({
            'close': [100.0, 102.0, 101.0, 103.0, 104.0, 105.0, 103.0, 102.0, 104.0, 106.0],
        })
        
        result = analytics.calculate_rsi(df, period=5)
        
        assert 'rsi' in result.columns
        # RSI 应该在 0-100 之间
        rsi_values = result['rsi'].drop_nulls().to_list()
        for v in rsi_values:
            assert 0 <= v <= 100
    
    def test_cross_sectional_rank_works(self):
        """测试截面排名真正工作"""
        from data_svc.analytics.polars_analytics import PolarsAnalytics
        
        analytics = PolarsAnalytics()
        
        df = pl.DataFrame({
            'stock_code': ['A', 'B', 'C', 'A', 'B', 'C'],
            'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02', '2024-01-02'],
            'close': [100.0, 200.0, 150.0, 110.0, 210.0, 140.0],
        })
        
        result = analytics.cross_sectional_rank(df, column='close')
        
        assert 'close_rank' in result.columns


class TestOptimizedDataQueryPolars:
    """测试 OptimizedStockDataQuery 使用 Polars"""
    
    def test_data_query_uses_polars(self):
        """测试数据查询使用 Polars"""
        from data_svc.database.optimized_data_query import OptimizedStockDataQuery
        import inspect
        
        source = inspect.getsource(OptimizedStockDataQuery)
        assert 'import polars' in source or 'polars as pl' in source
        assert 'pl.read_parquet' in source or 'pl.scan_parquet' in source
        assert 'duckdb.connect' not in source


class TestDataInterfacePolars:
    """测试 unified_data_interface 使用 Polars"""
    
    def test_data_interface_uses_polars(self):
        """测试数据接口使用 Polars"""
        from data_svc.unified_data_interface import UnifiedDataInterface
        import inspect
        
        source = inspect.getsource(UnifiedDataInterface)
        assert 'PolarsAnalytics' in source or 'polars' in source
        assert 'duckdb' not in source


class TestNoDuckdbFilesExist:
    """测试 DuckDB 文件不存在"""
    
    def test_duck_analyzer_deleted(self):
        """测试 duck_analyzer.py 已删除"""
        duck_file = project_root / "data_svc" / "store" / "duck_analyzer.py"
        assert not duck_file.exists(), "duck_analyzer.py 应该被删除"
    
    def test_duckdb_analytics_deleted(self):
        """测试 duckdb_analytics.py 已删除"""
        duck_file = project_root / "data_svc" / "analytics" / "duckdb_analytics.py"
        assert not duck_file.exists(), "duckdb_analytics.py 应该被删除"


class TestConfigNoDuckdb:
    """测试配置中没有 DuckDB"""
    
    def test_setting_no_duckdb_config(self):
        """测试 setting.py 没有 DuckDB 配置"""
        from config import setting
        import inspect
        
        source = inspect.getsource(setting)
        assert 'DUCKDB' not in source
        assert 'duckdb' not in source.lower()
    
    def test_config_no_duckdb(self):
        """测试 config.py 没有 DuckDB"""
        config_file = project_root / "config" / "config.py"
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'duckdb' not in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
