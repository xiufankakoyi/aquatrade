"""
FactorMatrix 因子矩阵构建测试

测试内容：
1. FactorMatrix 数据结构验证
2. 因子矩阵形状和类型验证
3. 日期索引映射验证
4. 股票代码索引映射验证
5. 因子数据访问验证
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from core.backtest.factor_matrix import FactorMatrix


class TestFactorMatrixStructure:
    """FactorMatrix 数据结构测试"""
    
    def test_factor_matrix_creation(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """测试因子矩阵创建"""
        factor_names = ['open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10', 'ma20']
        
        date_to_idx = {d: i for i, d in enumerate(sample_trading_dates)}
        code_to_idx = {c: i for i, c in enumerate(sample_stock_codes)}
        
        fm = FactorMatrix(
            values=sample_factor_matrix,
            dates=sample_trading_dates,
            codes_int=np.array([int(c) for c in sample_stock_codes], dtype=np.int32),
            codes_str=sample_stock_codes,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
        
        assert fm.values.shape == sample_factor_matrix.shape
        assert len(fm.dates) == len(sample_trading_dates)
        assert len(fm.codes_str) == len(sample_stock_codes)
        assert len(fm.factor_names) == 8
    
    def test_factor_matrix_shape(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """测试因子矩阵形状"""
        T = len(sample_trading_dates)
        N = len(sample_stock_codes)
        F = 8
        
        assert sample_factor_matrix.shape == (T, N, F)
    
    def test_factor_matrix_dtypes(self, sample_factor_matrix):
        """测试因子矩阵数据类型"""
        assert sample_factor_matrix.dtype == np.float32
    
    def test_factor_matrix_values_range(self, sample_factor_matrix):
        """测试因子矩阵值范围"""
        open_prices = sample_factor_matrix[:, :, 0]
        close_prices = sample_factor_matrix[:, :, 3]
        
        assert np.all(open_prices > 0)
        assert np.all(close_prices > 0)


class TestFactorMatrixIndexing:
    """FactorMatrix 索引测试"""
    
    @pytest.fixture
    def factor_matrix(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """创建因子矩阵实例"""
        factor_names = ['open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10', 'ma20']
        
        date_to_idx = {d: i for i, d in enumerate(sample_trading_dates)}
        code_to_idx = {c: i for i, c in enumerate(sample_stock_codes)}
        
        return FactorMatrix(
            values=sample_factor_matrix,
            dates=sample_trading_dates,
            codes_int=np.array([int(c) for c in sample_stock_codes], dtype=np.int32),
            codes_str=sample_stock_codes,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
    
    def test_date_to_idx_mapping(self, factor_matrix, sample_trading_dates):
        """测试日期到索引映射"""
        for i, date in enumerate(sample_trading_dates):
            assert factor_matrix.date_to_idx[date] == i
    
    def test_code_to_idx_mapping(self, factor_matrix, sample_stock_codes):
        """测试股票代码到索引映射"""
        for i, code in enumerate(sample_stock_codes):
            assert factor_matrix.code_to_idx[code] == i
    
    def test_get_day_data(self, factor_matrix, sample_trading_dates):
        """测试获取某天数据"""
        first_date = sample_trading_dates[0]
        day_data = factor_matrix.get_day_data(first_date)
        
        assert day_data is not None
        assert day_data.shape[1] == 8  # 8 个因子
    
    def test_get_day_data_invalid_date(self, factor_matrix):
        """测试获取无效日期数据"""
        day_data = factor_matrix.get_day_data("2099-01-01")
        
        assert day_data is None
    
    def test_get_day_index(self, factor_matrix, sample_trading_dates):
        """测试获取日期索引"""
        first_date = sample_trading_dates[0]
        idx = factor_matrix.get_day_index(first_date)
        
        assert idx == 0
    
    def test_get_day_index_invalid(self, factor_matrix):
        """测试获取无效日期索引"""
        idx = factor_matrix.get_day_index("2099-01-01")
        
        assert idx == -1
    
    def test_get_factor(self, factor_matrix):
        """测试获取因子数据"""
        close_prices = factor_matrix.get_factor('close')
        
        assert close_prices is not None
        assert close_prices.shape[0] == len(factor_matrix.dates)
        assert close_prices.shape[1] == len(factor_matrix.codes_str)
    
    def test_get_factor_invalid(self, factor_matrix):
        """测试获取无效因子"""
        invalid_factor = factor_matrix.get_factor('invalid_factor')
        
        assert invalid_factor is None


class TestFactorMatrixDateAlignment:
    """因子矩阵日期对齐测试"""
    
    def test_date_format_normalization(self):
        """测试日期格式标准化"""
        dates_with_time = ["2025-06-03 00:00:00", "2025-06-04 00:00:00"]
        dates_without_time = ["2025-06-03", "2025-06-04"]
        
        normalized = [d.split(' ')[0] if ' ' in d else d for d in dates_with_time]
        
        assert normalized == dates_without_time
    
    def test_datetime_to_string_conversion(self):
        """测试 datetime 到字符串转换"""
        dt = datetime(2025, 6, 3, 0, 0, 0)
        
        str_with_time = str(dt)
        str_without_time = dt.strftime("%Y-%m-%d")
        
        assert str_with_time == "2025-06-03 00:00:00"
        assert str_without_time == "2025-06-03"
    
    def test_date_slice_extraction(self):
        """测试日期切片提取"""
        date_str = "2025-06-03 00:00:00"
        date_only = date_str[:10]
        
        assert date_only == "2025-06-03"


class TestFactorMatrixPriceLogic:
    """因子矩阵价格逻辑测试"""
    
    @pytest.fixture
    def factor_matrix(self, sample_factor_matrix, sample_trading_dates, sample_stock_codes):
        """创建因子矩阵实例"""
        factor_names = ['open', 'high', 'low', 'close', 'volume', 'ma5', 'ma10', 'ma20']
        
        date_to_idx = {d: i for i, d in enumerate(sample_trading_dates)}
        code_to_idx = {c: i for i, c in enumerate(sample_stock_codes)}
        
        return FactorMatrix(
            values=sample_factor_matrix,
            dates=sample_trading_dates,
            codes_int=np.array([int(c) for c in sample_stock_codes], dtype=np.int32),
            codes_str=sample_stock_codes,
            factor_names=factor_names,
            date_to_idx=date_to_idx,
            code_to_idx=code_to_idx
        )
    
    def test_high_ge_low(self, factor_matrix):
        """测试最高价 >= 最低价"""
        high_prices = factor_matrix.get_factor('high')
        low_prices = factor_matrix.get_factor('low')
        
        assert np.all(high_prices >= low_prices)
    
    def test_high_ge_open_close(self, factor_matrix):
        """测试最高价 >= 开盘价和收盘价"""
        high_prices = factor_matrix.get_factor('high')
        open_prices = factor_matrix.get_factor('open')
        close_prices = factor_matrix.get_factor('close')
        
        assert np.all(high_prices >= open_prices)
        assert np.all(high_prices >= close_prices)
    
    def test_low_le_open_close(self, factor_matrix):
        """测试最低价 <= 开盘价和收盘价"""
        low_prices = factor_matrix.get_factor('low')
        open_prices = factor_matrix.get_factor('open')
        close_prices = factor_matrix.get_factor('close')
        
        assert np.all(low_prices <= open_prices)
        assert np.all(low_prices <= close_prices)
    
    def test_volume_positive(self, factor_matrix):
        """测试成交量为正"""
        volume = factor_matrix.get_factor('volume')
        
        assert np.all(volume > 0)
    
    def test_ma_ordering(self, factor_matrix):
        """测试均线顺序（短期均线波动更大）"""
        ma5 = factor_matrix.get_factor('ma5')
        ma10 = factor_matrix.get_factor('ma10')
        ma20 = factor_matrix.get_factor('ma20')
        
        ma5_std = np.std(ma5)
        ma10_std = np.std(ma10)
        ma20_std = np.std(ma20)
        
        assert ma5_std >= ma10_std
        assert ma10_std >= ma20_std


class TestFactorMatrixNaNHandling:
    """因子矩阵 NaN 处理测试"""
    
    def test_nan_detection(self):
        """测试 NaN 检测"""
        arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        
        nan_mask = np.isnan(arr)
        non_nan_count = np.sum(~nan_mask)
        
        assert non_nan_count == 3
    
    def test_nan_filtering(self):
        """测试 NaN 过滤"""
        arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        
        filtered = arr[~np.isnan(arr)]
        
        assert len(filtered) == 3
        assert list(filtered) == [1.0, 3.0, 5.0]
    
    def test_nan_fill_with_zero(self):
        """测试用 0 填充 NaN"""
        arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        
        filled = np.nan_to_num(arr, nan=0.0)
        
        assert list(filled) == [1.0, 0.0, 3.0, 0.0, 5.0]
    
    def test_nan_fill_with_mean(self):
        """测试用均值填充 NaN"""
        arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        
        mean_val = np.nanmean(arr)
        filled = np.where(np.isnan(arr), mean_val, arr)
        
        assert filled[1] == 3.0
        assert filled[3] == 3.0
