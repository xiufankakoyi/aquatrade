#!/usr/bin/env python3
"""
检查用户的回测结果
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config.config import Config

def check_user_backtests():
    """检查用户的回测结果"""
    print("=== 检查用户回测结果 ===")
    
    # 连接数据库
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 检查非测试回测结果
        print("\n1. 非测试回测结果:")
        cursor.execute("SELECT id, strategy_name, start_date, end_date, final_capital, trade_count FROM backtest_results WHERE strategy_name != 'TestStrategy' ORDER BY created_at DESC")
        backtests = cursor.fetchall()
        
        if not backtests:
            print("   没有非测试回测结果")
        else:
            print(f"   找到 {len(backtests)} 条非测试回测结果:")
            for bt in backtests:
                print(f"   - ID: {bt[0]}, 策略: {bt[1]}, 开始: {bt[2]}, 结束: {bt[3]}, 最终资金: {bt[4]}, 交易次数: {bt[5]}")
                
                # 检查对应的交易记录
                cursor.execute(f"SELECT COUNT(*) FROM trade_records WHERE backtest_id = {bt[0]}")
                trade_count = cursor.fetchone()[0]
                print(f"     对应的交易记录数量: {trade_count}")
        
        # 2. 检查所有回测结果
        print("\n2. 所有回测结果:")
        cursor.execute("SELECT COUNT(*) FROM backtest_results")
        total = cursor.fetchone()[0]
        print(f"   总回测结果数量: {total}")
        
        # 3. 检查所有交易记录
        print("\n3. 所有交易记录:")
        cursor.execute("SELECT COUNT(*) FROM trade_records")
        total_trades = cursor.fetchone()[0]
        print(f"   总交易记录数量: {total_trades}")
        
    finally:
        conn.close()
    
    print("\n=== 检查完成 ===")

if __name__ == "__main__":
    check_user_backtests()
