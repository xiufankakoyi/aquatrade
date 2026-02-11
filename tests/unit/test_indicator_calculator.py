# tests/unit/test_indicator_calculator.py
import pytest
import pandas as pd
import numpy as np
from core.utils.indicator_calculator import IndicatorCalculator

@pytest.fixture
def sample_data():
    """生成简单的测试数据"""
    dates = pd.date_range("2024-01-01", periods=100)
    # 生成一些递增序列用于验证 MA
    data = {
        'trade_date': dates,
        'close': [float(i) for i in range(100)],
        'high': [float(i + 1) for i in range(100)],
        'low': [float(max(0, i - 1)) for i in range(100)],
        'stock_code': ['000001'] * 50 + ['000002'] * 50
    }
    return pd.DataFrame(data)

def test_calculate_ma_single_stock(sample_data):
    calculator = IndicatorCalculator()
    df_001 = sample_data[sample_data['stock_code'] == '000001']
    
    window = 5
    ma5 = calculator.calculate_ma(df_001, window=window)
    
    # 窗口前应该是 NaN
    assert np.isnan(ma5.iloc[0])
    assert np.isnan(ma5.iloc[window-2])
    
    # 第5个值 (0+1+2+3+4)/5 = 2.0
    assert ma5.iloc[window-1] == 2.0
    # 第6个值 (1+2+3+4+5)/5 = 3.0
    assert ma5.iloc[window] == 3.0

def test_calculate_ma_with_groupby(sample_data):
    calculator = IndicatorCalculator()
    
    window = 5
    ma5 = calculator.calculate_ma(sample_data, window=window, group_by='stock_code')
    
    # 检查第二只股票的起始点 (index 50)
    # 如果不分分组，这里应该是前四个值的延续。如果分组，这里应该是 NaN。
    assert np.isnan(ma5.iloc[50])
    # 第 54 个位置 (index 54) 应该是第二组的前 5 项均值
    # 50, 51, 52, 53, 54 -> sum=260, mean=52.0
    assert ma5.iloc[54] == 52.0

def test_calculate_atr(sample_data):
    calculator = IndicatorCalculator()
    atr = calculator.calculate_atr(sample_data, window=10)
    
    assert len(atr) == 100
    assert not np.isnan(atr.iloc[9])
    assert np.isnan(atr.iloc[8])

def test_calculate_batch(sample_data):
    calculator = IndicatorCalculator()
    configs = [
        {'type': 'ma', 'window': 5, 'name': 'ma5'},
        {'type': 'ma', 'window': 10, 'name': 'ma10'}
    ]
    result_df = calculator.calculate_batch(sample_data, configs)
    
    assert 'ma5' in result_df.columns
    assert 'ma10' in result_df.columns
    assert result_df['ma5'].iloc[4] == 2.0
