#!/usr/bin/env python3
"""
检查数据库中的回测数据
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from config.config import Config

def check_backtest_data():
    """检查数据库中的回测数据"""
    print("=== 检查回测数据 ===")
    
    # 连接数据库
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查回测结果表
        print("\n1. 回测结果表 (backtest_results):")
        cursor.execute("SELECT * FROM backtest_results ORDER BY id DESC LIMIT 5")
        backtests = cursor.fetchall()
        
        if not backtests:
            print("   没有回测结果")
        else:
            # 打印列名
            cursor.execute("PRAGMA table_info(backtest_results)")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"   列名: {', '.join(columns[:10])}...")
            
            # 打印最近5条回测结果
            print(f"   最近 {len(backtests)} 条回测结果:")
            for backtest in backtests:
                print(f"   - ID: {backtest[0]}, 策略: {backtest[1]}, 开始日期: {backtest[2]}, 结束日期: {backtest[3]}, 最终资金: {backtest[5]:.2f}, 交易次数: {backtest[13]}")
                
                # 检查对应的交易记录
                cursor.execute(f"SELECT COUNT(*) FROM trade_records WHERE backtest_id = {backtest[0]}")
                trade_count = cursor.fetchone()[0]
                print(f"     交易记录数量: {trade_count}")
                
                # 如果有交易记录，打印最近3条
                if trade_count > 0:
                    cursor.execute(f"SELECT * FROM trade_records WHERE backtest_id = {backtest[0]} ORDER BY id DESC LIMIT 3")
                    trades = cursor.fetchall()
                    for trade in trades:
                        # 安全处理profit_loss字段
                        profit_loss = trade[8]
                        try:
                            profit_loss = float(profit_loss)
                            profit_loss_str = f"{profit_loss:.2f}"
                        except (ValueError, TypeError):
                            profit_loss_str = str(profit_loss)
                        
                        print(f"     - 交易: {trade[4]} {trade[2]} {trade[3]} {trade[6]}股 @ {float(trade[5]):.2f} 盈亏: {profit_loss_str}")
    
    finally:
        conn.close()
    
    print("\n=== 检查完成 ===")

if __name__ == "__main__":
    check_backtest_data()
