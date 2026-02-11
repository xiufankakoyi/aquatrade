#!/usr/bin/env python3
"""
初始化数据库表结构
"""

import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from data_svc.database.db_utils import ensure_tables, ensure_indexes, apply_performance_pragmas
from config.config import Config

def init_database():
    """初始化数据库"""
    print("=== 初始化数据库 ===")
    
    # 检查数据库目录是否存在
    db_path = Config.DB_PATH
    db_dir = os.path.dirname(db_path)
    print(f"数据库路径: {db_path}")
    print(f"数据库目录: {db_dir}")
    
    # 创建数据库目录（如果不存在）
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print("创建数据库目录成功")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    print("连接数据库成功")
    
    try:
        # 应用性能优化参数
        apply_performance_pragmas(conn)
        print("应用性能优化参数成功")
        
        # 创建表
        ensure_tables(conn)
        print("创建表成功")
        
        # 创建索引
        ensure_indexes(conn)
        print("创建索引成功")
        
        # 提交事务
        conn.commit()
        print("提交事务成功")
    except Exception as e:
        print(f"初始化数据库失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    print("\n=== 数据库初始化完成 ===")
    return True

if __name__ == "__main__":
    init_database()
