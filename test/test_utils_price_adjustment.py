"""
core/utils/price_adjustment.py 价格复权测试

测试内容：
1. 前复权计算（Pandas 版本）
2. 前复权计算（Polars 版本）
3. 边界条件处理
4. 价格列处理
"""

import pytest
import pandas as pd
import numpy as np


class TestPriceAdjustmentConstants:
    """价格复权常量测试"""
    
    def test_price_columns_defined(self):
        """测试价格列定义"""
        from core.utils.price_adjustment import PRICE_COLUMNS
        
        assert 'open' in PRICE_COLUMNS
        assert 'high' in PRICE_COLUMNS
        assert 'low' in PRICE_COLUMNS
        assert 'close' in PRICE_COLUMNS
        assert 'prev_close' in PRICE_COLUMNS
    
    def test_limit_columns_not_included(self):
        """测试涨跌停价格不应被复权"""
        from core.utils.price_adjustment import PRICE_COLUMNS
        
        assert 'limit_up' not in PRICE_COLUMNS
        assert 'limit_down' not in PRICE_COLUMNS


class TestApplyForwardAdjustmentPandas:
    """Pandas 版本前复权测试"""
    
    def test_apply_adjustment_basic(self):
        """测试基本前复权计算"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 1.0, 1.0],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
    
    def test_apply_adjustment_with_factor(self):
        """测试带复权因子的前复权"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert 'close_adj' in result.columns
        assert result['close_adj'].iloc[0] == 10.0
        assert abs(result['close_adj'].iloc[1] - 9.9) < 0.01
        assert abs(result['close_adj'].iloc[2] - 9.6) < 0.01
    
    def test_apply_adjustment_empty_df(self):
        """测试空 DataFrame"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame()
        result = apply_forward_adjustment(df)
        
        assert result is None or result.empty
    
    def test_apply_adjustment_none_df(self):
        """测试 None DataFrame"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        result = apply_forward_adjustment(None)
        
        assert result is None
    
    def test_apply_adjustment_no_adj_column(self):
        """测试缺少复权因子列"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert 'close_adj' not in result.columns
    
    def test_apply_adjustment_all_factors_one(self):
        """测试所有因子为 1"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 1.0, 1.0],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
    
    def test_apply_adjustment_multiple_columns(self):
        """测试多列复权"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'open': [10.0, 11.0, 12.0],
            'high': [11.0, 12.0, 13.0],
            'low': [9.0, 10.0, 11.0],
            'close': [10.5, 11.5, 12.5],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment(df)
        
        assert 'open_adj' in result.columns
        assert 'high_adj' in result.columns
        assert 'low_adj' in result.columns
        assert 'close_adj' in result.columns
    
    def test_apply_adjustment_extra_columns(self):
        """测试额外列复权"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'custom_price': [5.0, 6.0, 7.0],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment(df, extra_columns=['custom_price'])
        
        assert 'close_adj' in result.columns
        assert 'custom_price_adj' in result.columns
    
    def test_apply_adjustment_missing_column(self):
        """测试列不存在时的情况"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment(df, extra_columns=['nonexistent'])
        
        assert result is not None
        assert 'close_adj' in result.columns


class TestApplyForwardAdjustmentPolars:
    """Polars 版本前复权测试"""
    
    def test_apply_adjustment_pl_basic(self):
        """测试 Polars 基本前复权"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 1.0, 1.0],
        })
        
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
        assert 'close_adj' in result.columns
    
    def test_apply_adjustment_pl_with_factor(self):
        """测试 Polars 带复权因子"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
        assert 'close_adj' in result.columns
    
    def test_apply_adjustment_pl_empty(self):
        """测试 Polars 空 DataFrame"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame()
        result = apply_forward_adjustment_pl(df)
        
        assert result is None or result.is_empty()
    
    def test_apply_adjustment_pl_none(self):
        """测试 Polars None"""
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        result = apply_forward_adjustment_pl(None)
        
        assert result is None
    
    def test_apply_adjustment_pl_no_adj_column(self):
        """测试 Polars 缺少复权因子列"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'close': [10.0, 11.0, 12.0],
        })
        
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
        assert 'close_adj' not in result.columns
    
    def test_apply_adjustment_pl_multiple_columns(self):
        """测试 Polars 多列复权"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'open': [10.0, 11.0, 12.0],
            'high': [11.0, 12.0, 13.0],
            'low': [9.0, 10.0, 11.0],
            'close': [10.5, 11.5, 12.5],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment_pl(df)
        
        assert 'open_adj' in result.columns
        assert 'high_adj' in result.columns
        assert 'low_adj' in result.columns
        assert 'close_adj' in result.columns


class TestPriceAdjustmentEdgeCases:
    """价格复权边界条件测试"""
    
    def test_nan_values(self):
        """测试 NaN 值处理"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, np.nan, 12.0],
            'adj_factor': [1.0, 0.9, 0.8],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert 'close_adj' in result.columns
    
    def test_zero_factor(self):
        """测试零因子"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 0.0, 0.8],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert result['close_adj'].iloc[1] == 0.0
    
    def test_negative_factor(self):
        """测试负因子"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, -0.5, 0.8],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
    
    def test_very_large_factor(self):
        """测试大因子"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 100.0, 1000.0],
        })
        
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert result['close_adj'].iloc[1] == 1100.0
