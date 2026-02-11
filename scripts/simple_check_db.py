#!/usr/bin/env python3
"""
简单检查数据库结构和数据
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config.config import Config

def simple_check():
    """简单检查数据库"""
    print("=== 简单数据库检查 ===")
    
    # 连接数据库
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 检查trade_records表结构
        print("\n1. trade_records表结构:")
        cursor.execute("PRAGMA table_info(trade_records)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   - {col[0]}: {col[1]} ({col[2]})")
        
        # 2. 检查backtest_results表数据
        print("\n2. backtest_results表数据:")
        cursor.execute("SELECT id, strategy_name, start_date, end_date, final_capital, trade_count FROM backtest_results ORDER BY id DESC")
        backtests = cursor.fetchall()
        for bt in backtests:
            print(f"   - ID: {bt[0]}, 策略: {bt[1]}, 开始: {bt[2]}, 结束: {bt[3]}, 最终资金: {bt[4]}, 交易次数: {bt[5]}")
        
        # 3. 检查trade_records表数据
        print("\n3. trade_records表数据:")
        cursor.execute("SELECT backtest_id, COUNT(*) FROM trade_records GROUP BY backtest_id")
        trade_counts = cursor.fetchall()
        for bt_id, count in trade_counts:
            print(f"   - 回测ID {bt_id}: {count} 条交易记录")
        
        # 4. 查看最近几条交易记录
        print("\n4. 最近5条交易记录:")
        cursor.execute("SELECT * FROM trade_records ORDER BY id DESC LIMIT 5")
        trades = cursor.fetchall()
        for trade in trades:
            print(f"   - {trade}")
    
    finally:
        conn.close()
    
    print("\n=== 检查完成 ===")

if __name__ == "__main__":
    simple_check()
