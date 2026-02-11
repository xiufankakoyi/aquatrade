# tests/schema/test_identify_columns.py
import pytest
from data_svc.database.optimized_data_query import OptimizedStockDataQuery

def test_print_all_table_schemas():
    """该测试用于扫描当前后端并打印所有表的列名，方便开发者了解数据库结构"""
    db = OptimizedStockDataQuery()
    tables = ["stock_daily", "stock_info", "benchmark_data", "stock_limit_status"]
    
    print("\n" + "="*50)
    print("DATABASE SCHEMA IDENTIFICATION")
    print("="*50)
    
    for table in tables:
        try:
            columns = db._get_table_columns(table)
            print(f"\n[TABLE: {table}]")
            if not columns:
                print("  (Empty or Table not found)")
            else:
                for idx, col in enumerate(sorted(list(columns)), 1):
                    print(f"  {idx:2d}. {col}")
        except Exception as e:
            print(f"\n[TABLE: {table}] - Error: {e}")
    
    print("\n" + "="*50)

def test_verify_critical_columns():
    """验证最关键的字段是否存在，防止策略逻辑崩溃"""
    db = OptimizedStockDataQuery()
    
    # 获取 stock_daily 的列
    daily_cols = db._get_table_columns("stock_daily")
    
    # 策略 JQVolumeStrategy 需要的必须字段
    critical_for_strategy = ['total_mv', 'volume_ratio', 'trade_date', 'stock_code']
    
    for col in critical_for_strategy:
        assert col in daily_cols, f"策略关键列丢失: {col} 不在 stock_daily 中"
