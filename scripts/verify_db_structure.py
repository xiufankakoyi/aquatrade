#!/usr/bin/env python3
"""
验证数据库结构和数据持久化功能
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config.config import Config

def verify_db_structure():
    """验证数据库表结构"""
    print("=== 验证数据库结构 ===")
    
    # 检查数据库文件是否存在
    db_path = Config.DB_PATH
    print(f"数据库路径: {db_path}")
    print(f"数据库存在: {os.path.exists(db_path)}")
    
    if not os.path.exists(db_path):
        print("错误: 数据库文件不存在")
        return False
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查表是否存在
        tables = ['backtest_results', 'trade_records', 'optimization_results']
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            result = cursor.fetchone()
            print(f"表 {table} 存在: {result is not None}")
            
            if result:
                # 查看表结构
                print(f"  表 {table} 结构:")
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                for col in columns:
                    print(f"    - {col[1]}: {col[2]}")
                
                # 查看数据量
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"    数据量: {count}")
    finally:
        conn.close()
    
    print("\n=== 验证完成 ===")
    return True

def test_backtest_data():
    """测试回测数据插入"""
    print("\n=== 测试回测数据插入 ===")
    
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 插入测试数据
        test_sql = """
            INSERT INTO backtest_results (
                strategy_name, start_date, end_date, initial_capital, final_capital, 
                total_return, annual_return, max_drawdown, sharpe_ratio, sortino_ratio, 
                win_rate, profit_factor, trade_count, params
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        test_params = (
            "TestStrategy",
            "2023-01-01",
            "2023-12-31",
            1000000,
            1200000,
            20.0,
            18.5,
            10.5,
            1.2,
            1.5,
            65.0,
            2.0,
            50,
            '{"param1": 10, "param2": 20}'
        )
        
        cursor.execute(test_sql, test_params)
        backtest_id = cursor.lastrowid
        print(f"插入测试回测结果成功，ID: {backtest_id}")
        
        # 插入交易记录
        trade_sql = """
            INSERT INTO trade_records (
                backtest_id, stock_code, stock_name, action, date, 
                price, shares, amount, profit_loss
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        trade_params = (
            backtest_id,
            "000001",
            "平安银行",
            "buy",
            "2023-01-10",
            10.0,
            1000,
            10000,
            0.0
        )
        
        cursor.execute(trade_sql, trade_params)
        print("插入测试交易记录成功")
        
        # 提交事务
        conn.commit()
        print("事务提交成功")
        
        # 验证数据
        cursor.execute(f"SELECT * FROM backtest_results WHERE id = {backtest_id}")
        backtest = cursor.fetchone()
        print(f"验证回测数据: {backtest is not None}")
        
        cursor.execute(f"SELECT * FROM trade_records WHERE backtest_id = {backtest_id}")
        trade = cursor.fetchone()
        print(f"验证交易记录: {trade is not None}")
        
        return True
    except Exception as e:
        print(f"错误: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    verify_db_structure()
    test_backtest_data()
