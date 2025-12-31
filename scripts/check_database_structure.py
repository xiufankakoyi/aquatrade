#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库结构检查脚本

检查所有数据库后端（LanceDB、DuckDB、SQLite）的表结构和数据统计
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.config import Config
from config.logger import get_logger

logger = get_logger(__name__)


def check_lancedb():
    """检查 LanceDB 数据库"""
    print("\n" + "=" * 80)
    print("[LanceDB] 数据库检查")
    print("=" * 80)
    
    try:
        import lancedb
        import pyarrow as pa
    except ImportError as e:
        print(f"[ERROR] LanceDB 或 PyArrow 未安装: {e}")
        return
    
    # LanceDB 数据目录
    parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
    lance_dir = Path(parquet_dir) / 'lance_db'
    
    if not lance_dir.exists():
        print(f"[WARN] LanceDB 目录不存在: {lance_dir}")
        return
    
    print(f"LanceDB 目录: {lance_dir}")
    
    try:
        db = lancedb.connect(str(lance_dir))
        table_names = db.table_names()
        
        if not table_names:
            print("[WARN] 未找到任何表")
            return
        
        print(f"[OK] 找到 {len(table_names)} 个表: {', '.join(table_names)}\n")
        
        for table_name in table_names:
            print(f"  表名: {table_name}")
            try:
                table = db.open_table(table_name)
                
                # 获取表结构
                schema = table.schema
                print(f"     列数: {len(schema)}")
                print(f"     列结构:")
                for field in schema:
                    print(f"       - {field.name}: {field.type}")
                
                # 获取数据统计
                try:
                    arrow_table = table.to_arrow()
                    num_rows = arrow_table.num_rows
                    print(f"     行数: {num_rows:,}")
                    
                    # 如果有 trade_date 列，显示日期范围
                    if 'trade_date' in arrow_table.column_names:
                        df = arrow_table.to_pandas()
                        dates = df['trade_date'].unique()
                        if len(dates) > 0:
                            dates_sorted = sorted(dates)
                            print(f"     日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]}")
                            print(f"     交易日数: {len(dates_sorted)}")
                    
                    # 如果有 stock_code 列，显示股票数量
                    if 'stock_code' in arrow_table.column_names:
                        df = arrow_table.to_pandas()
                        stocks = df['stock_code'].unique()
                        print(f"     股票数量: {len(stocks)}")
                    
                except Exception as e:
                    print(f"     [WARN] 无法获取数据统计: {e}")
                
                print()
                
            except Exception as e:
                print(f"     [ERROR] 打开表失败: {e}\n")
                
    except Exception as e:
        print(f"[ERROR] 连接 LanceDB 失败: {e}")


def check_duckdb():
    """检查 DuckDB 视图（从 Parquet 文件注册）"""
    print("\n" + "=" * 80)
    print("[DuckDB] 视图检查")
    print("=" * 80)
    
    try:
        import duckdb
    except ImportError:
        print("[ERROR] DuckDB 未安装")
        return
    
    parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
    parquet_path = Path(parquet_dir)
    
    print(f"Parquet 目录: {parquet_path}")
    
    if not parquet_path.exists():
        print(f"[WARN] Parquet 目录不存在: {parquet_path}")
        return
    
    # 连接 DuckDB
    conn = duckdb.connect()
    
    # 定义 Parquet 文件
    files = {
        "stock_daily": "stock_daily.parquet",
        "stock_info": "stock_info.parquet",
        "stock_limit_status": "stock_limit_status.parquet",
        "benchmark_data": "benchmark_daily.parquet"
    }
    
    print("\n检查 Parquet 文件:")
    for view_name, filename in files.items():
        file_path = parquet_path / filename
        abs_path = file_path.resolve()
        
        if file_path.exists():
            file_size = file_path.stat().st_size / (1024 * 1024)  # MB
            print(f"  [OK] {filename}: {file_size:.2f} MB")
            
            try:
                # 注册视图
                conn.execute(f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM parquet_scan('{abs_path}');
                """)
                
                # 获取表结构
                result = conn.execute(f"DESCRIBE {view_name}").fetchdf()
                print(f"     列数: {len(result)}")
                print(f"     列结构:")
                for _, row in result.iterrows():
                    print(f"       - {row['column_name']}: {row['column_type']}")
                
                # 获取行数
                count_result = conn.execute(f"SELECT COUNT(*) as cnt FROM {view_name}").fetchone()
                if count_result:
                    print(f"     行数: {count_result[0]:,}")
                
                # 如果有 trade_date 或 date 列，显示日期范围
                date_col = None
                if 'trade_date' in result['column_name'].values:
                    date_col = 'trade_date'
                elif 'date' in result['column_name'].values:
                    date_col = 'date'
                
                if date_col:
                    date_result = conn.execute(f"""
                        SELECT MIN({date_col}) as min_date, MAX({date_col}) as max_date,
                               COUNT(DISTINCT {date_col}) as date_count
                        FROM {view_name}
                    """).fetchone()
                    if date_result and date_result[0]:
                        print(f"     日期范围: {date_result[0]} ~ {date_result[1]}")
                        print(f"     交易日数: {date_result[2]}")
                
                # 如果有 stock_code 列，显示股票数量
                if 'stock_code' in result['column_name'].values:
                    stock_result = conn.execute(f"""
                        SELECT COUNT(DISTINCT stock_code) as stock_count
                        FROM {view_name}
                    """).fetchone()
                    if stock_result:
                        print(f"     股票数量: {stock_result[0]:,}")
                
                print()
                
            except Exception as e:
                print(f"     [ERROR] 注册视图失败: {e}\n")
        else:
            print(f"  [WARN] {filename}: 文件不存在")
    
    conn.close()


def check_sqlite():
    """检查 SQLite 数据库"""
    print("\n" + "=" * 80)
    print("[SQLite] 数据库检查")
    print("=" * 80)
    
    import sqlite3
    
    db_path = getattr(Config, 'DB_PATH', 'data/stock_data.db')
    db_file = Path(db_path)
    
    print(f"SQLite 数据库: {db_file}")
    
    if not db_file.exists():
        print(f"[WARN] SQLite 数据库文件不存在: {db_file}")
        return
    
    file_size = db_file.stat().st_size / (1024 * 1024)  # MB
    print(f"文件大小: {file_size:.2f} MB\n")
    
    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            print("[WARN] 未找到任何表")
            conn.close()
            return
        
        print(f"[OK] 找到 {len(tables)} 个表: {', '.join([t[0] for t in tables])}\n")
        
        for (table_name,) in tables:
            print(f"  表名: {table_name}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"     列数: {len(columns)}")
            print(f"     列结构:")
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                pk_str = " PRIMARY KEY" if pk else ""
                print(f"       - {col_name}: {col_type} {nullable}{pk_str}")
            
            # 获取行数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"     行数: {count:,}")
            
            # 如果有 trade_date 列，显示日期范围
            if any(col[1] == 'trade_date' for col in columns):
                cursor.execute(f"""
                    SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date,
                           COUNT(DISTINCT trade_date) as date_count
                    FROM {table_name}
                """)
                date_info = cursor.fetchone()
                if date_info and date_info[0]:
                    print(f"     日期范围: {date_info[0]} ~ {date_info[1]}")
                    print(f"     交易日数: {date_info[2]}")
            
            # 如果有 stock_code 列，显示股票数量
            if any(col[1] == 'stock_code' for col in columns):
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT stock_code) as stock_count
                    FROM {table_name}
                """)
                stock_count = cursor.fetchone()[0]
                print(f"     股票数量: {stock_count:,}")
            
            print()
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] 连接 SQLite 失败: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("数据库结构检查工具")
    print("=" * 80)
    print(f"项目根目录: {project_root}")
    print(f"Parquet 目录: {getattr(Config, 'PARQUET_DIR', 'parquet_data')}")
    print(f"SQLite 数据库: {getattr(Config, 'DB_PATH', 'data/stock_data.db')}")
    
    # 检查所有数据库
    check_lancedb()
    check_duckdb()
    check_sqlite()
    
    print("\n" + "=" * 80)
    print("[OK] 检查完成")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

