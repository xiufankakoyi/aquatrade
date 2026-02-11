#!/usr/bin/env python3
"""
调试交易记录问题
"""

import os
import glob
import sys

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=== 调试交易记录问题 ===\n")

# 1. 检查日志文件
print("1. 检查日志文件:")
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
log_files = glob.glob(os.path.join(logs_dir, '*.log'))

if not log_files:
    print("   没有找到日志文件")
else:
    # 按修改时间排序
    log_files.sort(key=os.path.getmtime, reverse=True)
    recent_log = log_files[0]
    print(f"   最近的日志文件: {recent_log}")
    
    # 读取最近100行日志
    with open(recent_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()[-100:]
    
    # 查找回测相关的日志
    backtest_logs = []
    for line in lines:
        if 'backtest' in line.lower() or 'trade' in line.lower() or 'db' in line.lower() or 'error' in line.lower():
            backtest_logs.append(line.strip())
    
    if backtest_logs:
        print(f"\n   最近的回测相关日志 ({len(backtest_logs)} 条):")
        for log in backtest_logs[-20:]:  # 只显示最近20条
            print(f"   - {log}")
    else:
        print("   没有找到回测相关的日志")

# 2. 检查数据库
print("\n2. 检查数据库:")
from config.config import Config
import sqlite3

# 连接数据库
db_path = Config.DB_PATH
print(f"   数据库路径: {db_path}")
print(f"   数据库存在: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查backtest_results表
        cursor.execute("SELECT COUNT(*) FROM backtest_results")
        backtest_count = cursor.fetchone()[0]
        print(f"   backtest_results表记录数: {backtest_count}")
        
        # 检查最近的回测记录
        cursor.execute("SELECT id, strategy_name, start_date, end_date, trade_count, created_at FROM backtest_results ORDER BY created_at DESC LIMIT 5")
        recent_backtests = cursor.fetchall()
        
        if recent_backtests:
            print(f"   最近 {len(recent_backtests)} 条回测记录:")
            for bt in recent_backtests:
                print(f"   - ID: {bt[0]}, 策略: {bt[1]}, 开始: {bt[2]}, 结束: {bt[3]}, 交易次数: {bt[4]}, 创建时间: {bt[5]}")
                
                # 检查对应的交易记录
                cursor.execute(f"SELECT COUNT(*) FROM trade_records WHERE backtest_id = {bt[0]}")
                trade_count = cursor.fetchone()[0]
                print(f"     对应的交易记录数: {trade_count}")
                
                # 如果有交易记录，查看最近几条
                if trade_count > 0:
                    cursor.execute(f"SELECT id, stock_code, action, date, profit_loss FROM trade_records WHERE backtest_id = {bt[0]} ORDER BY id DESC LIMIT 3")
                    trades = cursor.fetchall()
                    print(f"     最近 3 条交易记录:")
                    for trade in trades:
                        print(f"       - ID: {trade[0]}, 股票: {trade[1]}, 方向: {trade[2]}, 日期: {trade[3]}, 盈亏: {trade[4]}")
        
        # 检查trade_records表
        cursor.execute("SELECT COUNT(*) FROM trade_records")
        trade_count = cursor.fetchone()[0]
        print(f"\n   trade_records表记录数: {trade_count}")
        
        # 如果有交易记录，查看最近几条
        if trade_count > 0:
            cursor.execute("SELECT backtest_id, COUNT(*) FROM trade_records GROUP BY backtest_id ORDER BY COUNT(*) DESC")
            trade_counts = cursor.fetchall()
            print(f"   按回测ID分组的交易记录数:")
            for bt_id, count in trade_counts[:5]:
                print(f"   - 回测ID {bt_id}: {count} 条交易记录")
    finally:
        conn.close()

# 3. 检查回测引擎代码
print("\n3. 检查回测引擎代码:")
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
print(f"   OptimizedBacktestEngine 类路径: {OptimizedBacktestEngine.__module__}")
print(f"   run_backtest_streaming 方法存在: {'run_backtest_streaming' in dir(OptimizedBacktestEngine)}")

# 检查交易记录处理逻辑
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'backtest', 'optimized_backtest_engine.py'), 'r') as f:
    content = f.read()

# 检查关键函数和变量
trades_processing_start = content.find("# 6. 转换交易记录并产出")
trades_processing_end = content.find("# 7. 按日期顺序产出交易记录和权益数据", trades_processing_start)

if trades_processing_start > 0 and trades_processing_end > 0:
    print(f"   交易记录处理逻辑行数: {trades_processing_end - trades_processing_start} 行")
    print(f"   包含持仓跟踪字典: {'positions_tracker' in content[trades_processing_start:trades_processing_end]}")
    print(f"   包含FIFO盈亏计算: {'FIFO' in content[trades_processing_start:trades_processing_end] or 'profit_loss' in content[trades_processing_start:trades_processing_end]}")
else:
    print("   没有找到交易记录处理逻辑")

print("\n=== 调试完成 ===")
