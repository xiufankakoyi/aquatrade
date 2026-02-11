# tests/schema/test_db_structure.py
import pytest
import pandas as pd
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from config.config import Config

@pytest.fixture(scope="module")
def db_query():
    return OptimizedStockDataQuery()

def test_stock_daily_columns(db_query):
    """验证 stock_daily 表是否包含必要的核心字段"""
    # 核心字段列表
    required_columns = [
        'stock_code', 'trade_date', 'open', 'high', 'low', 'close', 
        'volume', 'amount', 'total_mv', 'adj_factor'
    ]
    
    # 获取列名集合
    columns = db_query._get_table_columns("stock_daily")
    
    missing = [col for col in required_columns if col not in columns]
    assert not missing, f"stock_daily 缺少核心字段: {missing}"

def test_stock_info_columns(db_query):
    """验证 stock_info 表是否包含必要的描述性字段"""
    required_columns = ['stock_code', 'stock_name']
    
    columns = db_query._get_table_columns("stock_info")
    
    missing = [col for col in required_columns if col not in columns]
    assert not missing, f"stock_info 缺少字段: {missing}"

def test_benchmark_data_columns(db_query):
    """验证 benchmark_data 表结构"""
    required_columns = ['code', 'date', 'close']
    
    columns = db_query._get_table_columns("benchmark_data")
    
    missing = [col for col in required_columns if col not in columns]
    assert not missing, f"benchmark_data 缺少字段: {missing}"

def test_stock_limit_status_columns(db_query):
    """验证涨跌停状态表结构"""
    required_columns = ['stock_code', 'trade_date', 'is_limit_up', 'is_limit_down', 'is_suspended']
    
    columns = db_query._get_table_columns("stock_limit_status")
    
    missing = [col for col in required_columns if col not in columns]
    assert not missing, f"stock_limit_status 缺少字段: {missing}"
