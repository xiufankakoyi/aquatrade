"""
core/utils/gpu_acceleration.py GPU加速工具补充测试

测试内容：
1. GPU 启用/禁用功能
2. CPU 回退路径
3. 滚动均值计算
4. 移动平均指标计算
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


class TestCheckGPUAvailability:
    """GPU可用性检测测试"""
    
    def test_check_gpu_availability_default(self):
        """测试默认GPU检测"""
        from core.utils.gpu_acceleration import check_gpu_availability
        
        result = check_gpu_availability()
        
        assert isinstance(result, dict)
        assert 'cupy' in result
        assert 'cudf' in result
        assert 'numba_cuda' in result
        assert 'any_available' in result
        assert 'device_count' in result
        assert isinstance(result['any_available'], bool)
    
    @patch('core.utils.gpu_acceleration.CUPY_AVAILABLE', True)
    @patch('core.utils.gpu_acceleration.cp')
    def test_check_gpu_availability_with_cupy(self, mock_cp):
        """测试CuPy可用时的检测"""
        from core.utils.gpu_acceleration import check_gpu_availability
        
        mock_cp.cuda.runtime.getDeviceCount.return_value = 1
        
        result = check_gpu_availability()
        
        assert result['cupy'] == True
    
    @patch('core.utils.gpu_acceleration.CUPY_AVAILABLE', True)
    @patch('core.utils.gpu_acceleration.CUDF_AVAILABLE', True)
    @patch('core.utils.gpu_acceleration.cp')
    def test_check_gpu_availability_with_multiple_gpu_libs(self, mock_cp):
        """测试多GPU库可用时的检测"""
        from core.utils.gpu_acceleration import check_gpu_availability
        
        mock_cp.cuda.runtime.getDeviceCount.return_value = 2
        
        result = check_gpu_availability()
        
        assert result['any_available'] == True


class TestGPUEnableDisable:
    """GPU启用禁用测试"""
    
    def test_disable_gpu(self):
        """测试禁用GPU"""
        from core.utils.gpu_acceleration import disable_gpu, USE_GPU
        
        disable_gpu()
        
        from core.utils.gpu_acceleration import USE_GPU as gpu_status
        assert gpu_status == False
    
    def test_enable_gpu_force_mode(self):
        """测试强制启用GPU"""
        from core.utils.gpu_acceleration import enable_gpu, disable_gpu
        
        disable_gpu()
        result = enable_gpu(force=True)
        
        assert result == True
    
    def test_is_gpu_enabled(self):
        """测试检查GPU是否启用"""
        from core.utils.gpu_acceleration import is_gpu_enabled, disable_gpu
        
        disable_gpu()
        result = is_gpu_enabled()
        
        assert isinstance(result, bool)


class TestRollingMeanGPU:
    """滚动均值计算测试"""
    
    def test_rolling_mean_cpu_fallback(self):
        """测试CPU回退路径"""
        from core.utils.gpu_acceleration import rolling_mean_gpu, disable_gpu
        
        disable_gpu()
        
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean_gpu(data, window=3)
        
        assert isinstance(result, np.ndarray)
    
    def test_rolling_mean_with_series(self):
        """测试Pandas Series输入"""
        from core.utils.gpu_acceleration import rolling_mean_gpu, disable_gpu
        
        disable_gpu()
        
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean_gpu(data, window=3)
        
        assert isinstance(result, np.ndarray)
    
    def test_rolling_mean_with_min_periods(self):
        """测试最小周期参数"""
        from core.utils.gpu_acceleration import rolling_mean_gpu, disable_gpu
        
        disable_gpu()
        
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean_gpu(data, window=3, min_periods=1)
        
        assert isinstance(result, np.ndarray)


class TestCalculateMAIndicatorsGPU:
    """移动平均指标计算测试"""
    
    def test_calculate_ma_cpu_fallback(self):
        """测试CPU回退路径"""
        from core.utils.gpu_acceleration import calculate_ma_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
            'stock_code': ['000001.SZ'] * 5
        })
        
        result = calculate_ma_indicators_gpu(
            df=df,
            columns=['close'],
            windows=[5],
            group_by='stock_code'
        )
        
        assert isinstance(result, pd.DataFrame)
        assert 'ma5_close' in result.columns
    
    def test_calculate_ma_without_group(self):
        """测试无分组计算"""
        from core.utils.gpu_acceleration import calculate_ma_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0]
        })
        
        result = calculate_ma_indicators_gpu(
            df=df,
            columns=['close'],
            windows=[3]
        )
        
        assert isinstance(result, pd.DataFrame)
        assert 'ma3_close' in result.columns
    
    def test_calculate_ma_multiple_columns(self):
        """测试多列计算"""
        from core.utils.gpu_acceleration import calculate_ma_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        result = calculate_ma_indicators_gpu(
            df=df,
            columns=['close', 'volume'],
            windows=[5, 5]
        )
        
        assert isinstance(result, pd.DataFrame)
        assert 'ma5_close' in result.columns
        assert 'ma5_volume' in result.columns


class TestBatchCalculateIndicatorsGPU:
    """批量计算指标测试"""
    
    def test_batch_calculate_indicators_cpu_fallback(self):
        """测试批量计算CPU回退"""
        from core.utils.gpu_acceleration import batch_calculate_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        stock_data_dict = {
            '000001.SZ': pd.DataFrame({
                'close': [10.0, 11.0, 12.0, 13.0, 14.0],
                'volume': [1000, 1100, 1200, 1300, 1400]
            }),
            '000002.SZ': pd.DataFrame({
                'close': [20.0, 21.0, 22.0, 23.0, 24.0],
                'volume': [2000, 2100, 2200, 2300, 2400]
            })
        }
        
        indicators = [
            {'name': 'ma5', 'column': 'close', 'window': 5, 'type': 'ma'}
        ]
        
        result = batch_calculate_indicators_gpu(stock_data_dict, indicators)
        
        assert isinstance(result, dict)
        assert '000001.SZ' in result
        assert 'ma5_close' in result['000001.SZ'].columns
    
    def test_batch_calculate_indicators_ema(self):
        """测试EMA指标"""
        from core.utils.gpu_acceleration import batch_calculate_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        stock_data_dict = {
            '000001.SZ': pd.DataFrame({
                'close': [10.0, 11.0, 12.0, 13.0, 14.0]
            })
        }
        
        indicators = [
            {'name': 'ema5', 'column': 'close', 'window': 5, 'type': 'ema'}
        ]
        
        result = batch_calculate_indicators_gpu(stock_data_dict, indicators)
        
        assert 'ema5_close' in result['000001.SZ'].columns
    
    def test_batch_calculate_indicators_std(self):
        """测试STD指标"""
        from core.utils.gpu_acceleration import batch_calculate_indicators_gpu, disable_gpu
        
        disable_gpu()
        
        stock_data_dict = {
            '000001.SZ': pd.DataFrame({
                'close': [10.0, 11.0, 12.0, 13.0, 14.0]
            })
        }
        
        indicators = [
            {'name': 'std5', 'column': 'close', 'window': 5, 'type': 'std'}
        ]
        
        result = batch_calculate_indicators_gpu(stock_data_dict, indicators)
        
        assert 'std5_close' in result['000001.SZ'].columns


class TestRollingMeanNumbaCUDA:
    """Numba CUDA滚动均值测试"""
    
    def test_rolling_mean_numba_cuda_cpu_fallback(self):
        """测试Numba CUDA CPU回退"""
        from core.utils.gpu_acceleration import rolling_mean_numba_cuda, disable_gpu
        
        disable_gpu()
        
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean_numba_cuda(data, window=3)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == len(data)
    
    def test_rolling_mean_numba_cuda_small_window(self):
        """测试小窗口"""
        from core.utils.gpu_acceleration import rolling_mean_numba_cuda, disable_gpu
        
        disable_gpu()
        
        data = np.array([1.0, 2.0, 3.0])
        result = rolling_mean_numba_cuda(data, window=2)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == 3
