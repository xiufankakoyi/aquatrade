"""
Pytest 配置文件

提供测试所需的 fixtures 和共享配置
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 设置环境变量
os.environ['DB_BACKEND'] = 'lancedb'

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_stock_codes() -> List[str]:
    """样本股票代码"""
    return ['000001', '000002', '600000', '600036', '000333']


@pytest.fixture
def sample_trading_dates() -> List[str]:
    """样本交易日期（10天）"""
    dates = []
    start = datetime(2025, 6, 2)
    for i in range(10):
        d = start + timedelta(days=i)
        if d.weekday() < 5:  # 跳过周末
            dates.append(d.strftime('%Y-%m-%d'))
    return dates


@pytest.fixture
def sample_price_data(sample_stock_codes, sample_trading_dates) -> pd.DataFrame:
    """生成样本价格数据"""
    np.random.seed(42)
    rows = []
    
    for code in sample_stock_codes:
        base_price = np.random.uniform(10, 100)
        for i, date in enumerate(sample_trading_dates):
            change = np.random.uniform(-0.05, 0.05)
            open_price = base_price * (1 + change)
            close_price = open_price * (1 + np.random.uniform(-0.03, 0.03))
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.02))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.02))
            volume = int(np.random.uniform(1000000, 10000000))
            
            rows.append({
                'trade_date': date,
                'stock_code': code,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'amount': volume * close_price,
                'adj_factor': 1.0,
                'is_st': 0,
                'is_suspended': 0,
                'is_limit_up': 0,
                'is_limit_down': 0,
                'total_mv': close_price * 100000000,
                'ma5': round(open_price * (1 + np.random.uniform(-0.02, 0.02)), 2),
                'ma10': round(open_price * (1 + np.random.uniform(-0.03, 0.03)), 2),
                'ma20': round(open_price * (1 + np.random.uniform(-0.04, 0.04)), 2),
            })
            base_price = close_price
    
    return pd.DataFrame(rows)


@pytest.fixture
def sample_factor_matrix(sample_stock_codes, sample_trading_dates) -> np.ndarray:
    """
    生成样本因子矩阵
    
    形状: (T, N, F)
    - T: 交易日数量
    - N: 股票数量
    - F: 因子数量 (open, high, low, close, volume, ma5, ma10, ma20)
    """
    np.random.seed(42)
    T = len(sample_trading_dates)
    N = len(sample_stock_codes)
    F = 8
    
    matrix = np.zeros((T, N, F), dtype=np.float32)
    
    for n in range(N):
        base_price = np.random.uniform(10, 100)
        for t in range(T):
            change = np.random.uniform(-0.05, 0.05)
            open_price = base_price * (1 + change)
            close_price = open_price * (1 + np.random.uniform(-0.03, 0.03))
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.02))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.02))
            
            matrix[t, n, 0] = open_price   # open
            matrix[t, n, 1] = high_price   # high
            matrix[t, n, 2] = low_price    # low
            matrix[t, n, 3] = close_price  # close
            matrix[t, n, 4] = np.random.uniform(1000000, 10000000)  # volume
            matrix[t, n, 5] = open_price * 0.98  # ma5
            matrix[t, n, 6] = open_price * 0.96  # ma10
            matrix[t, n, 7] = open_price * 0.94  # ma20
            
            base_price = close_price
    
    return matrix


@pytest.fixture
def sample_signal_matrix(sample_trading_dates, sample_stock_codes) -> np.ndarray:
    """
    生成样本信号矩阵
    
    形状: (T, N)
    - 0: 无信号
    - 1: 买入信号
    - -1: 卖出信号
    """
    np.random.seed(42)
    T = len(sample_trading_dates)
    N = len(sample_stock_codes)
    
    signals = np.zeros((T, N), dtype=np.int8)
    
    # 在第一天生成买入信号
    signals[0, :3] = 1  # 前3只股票买入
    
    # 在第5天生成卖出信号
    if T > 5:
        signals[5, :3] = -1
    
    # 在第3天生成更多买入信号
    if T > 3:
        signals[3, 3:] = 1
    
    return signals


@pytest.fixture
def backtest_config():
    """回测配置"""
    from core.backtest.unified_engine import BacktestConfig
    return BacktestConfig(
        initial_capital=1_000_000.0,
        commission_rate=0.0003,
        min_commission=5.0,
        sell_tax=0.001,
        position_ratio=0.1,
        warmup_days=5
    )


@pytest.fixture
def mock_data_query():
    """Mock 数据查询对象"""
    class MockDataQuery:
        def __init__(self):
            self._cache = {}
        
        def get_stock_daily(self, code, start_date, end_date):
            return pd.DataFrame()
        
        def get_trading_dates(self, start_date, end_date):
            return []
    
    return MockDataQuery()
