"""
core/utils/price_adjustment.py 价格复权测试

测试内容：
1. PRICE_COLUMNS 常量
2. apply_forward_adjustment 函数
3. apply_forward_adjustment_pl 函数
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestPriceColumns:
    """价格列常量测试"""
    
    def test_price_columns_contains_basic(self):
        """测试基本价格列"""
        from core.utils.price_adjustment import PRICE_COLUMNS
        
        assert 'open' in PRICE_COLUMNS
        assert 'high' in PRICE_COLUMNS
        assert 'low' in PRICE_COLUMNS
        assert 'close' in PRICE_COLUMNS
    
    def test_price_columns_contains_ma(self):
        """测试均线列"""
        from core.utils.price_adjustment import PRICE_COLUMNS
        
        assert 'ma5' in PRICE_COLUMNS
        assert 'ma10' in PRICE_COLUMNS
        assert 'ma20' in PRICE_COLUMNS


class TestApplyForwardAdjustment:
    """前复权调整测试"""
    
    def test_apply_forward_adjustment_none(self):
        """测试 None 输入"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        result = apply_forward_adjustment(None)
        
        assert result is None
    
    def test_apply_forward_adjustment_empty(self):
        """测试空 DataFrame"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame()
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert result.empty
    
    def test_apply_forward_adjustment_no_adj_factor(self):
        """测试无复权因子列"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0]
        })
        result = apply_forward_adjustment(df)
        
        assert result is not None
    
    def test_apply_forward_adjustment_basic(self):
        """测试基本复权"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 1.0, 1.0]
        })
        result = apply_forward_adjustment(df)
        
        assert result is not None
    
    def test_apply_forward_adjustment_with_factor(self):
        """测试带复权因子"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.1, 1.1, 1.1]
        })
        result = apply_forward_adjustment(df)
        
        assert result is not None
        assert 'close_adj' in result.columns
    
    def test_apply_forward_adjustment_extra_columns(self):
        """测试额外列复权"""
        from core.utils.price_adjustment import apply_forward_adjustment
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'custom_price': [9.0, 10.0, 11.0],
            'adj_factor': [1.1, 1.1, 1.1]
        })
        result = apply_forward_adjustment(df, extra_columns=['custom_price'])
        
        assert result is not None
        assert 'close_adj' in result.columns
        assert 'custom_price_adj' in result.columns


class TestApplyForwardAdjustmentPl:
    """Polars 前复权调整测试"""
    
    def test_apply_forward_adjustment_pl_none(self):
        """测试 None 输入"""
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        result = apply_forward_adjustment_pl(None)
        
        assert result is None
    
    def test_apply_forward_adjustment_pl_empty(self):
        """测试空 DataFrame"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame()
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
    
    def test_apply_forward_adjustment_pl_no_adj_factor(self):
        """测试无复权因子列"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'close': [10.0, 11.0, 12.0]
        })
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
    
    def test_apply_forward_adjustment_pl_basic(self):
        """测试基本复权"""
        import polars as pl
        from core.utils.price_adjustment import apply_forward_adjustment_pl
        
        df = pl.DataFrame({
            'close': [10.0, 11.0, 12.0],
            'adj_factor': [1.0, 1.0, 1.0]
        })
        result = apply_forward_adjustment_pl(df)
        
        assert result is not None
