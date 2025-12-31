#!/usr/bin/env python3
"""
导出 SQLite 数据库中的 benchmark 数据到 Parquet 格式
"""
import sqlite3
import pandas as pd
import os
import sys
from pathlib import Path

# 动态添加项目根目录
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.config import Config


def export_benchmark():
    """导出 benchmark 数据到 Parquet"""
    db_path = Config.DB_PATH
    parquet_dir = Path(Config.PARQUET_DIR)
    
    print(f"正在连接数据库: {db_path}")
    if not os.path.exists(db_path):
        print(f"[错误] 数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    
    try:
        # 读取基准数据
        # 注意：保持 'code' 列名，与现有查询逻辑保持一致
        print("正在读取 benchmark_data 表...")
        df = pd.read_sql("SELECT date, code, close FROM benchmark_data ORDER BY code, date", conn)
        
        if df.empty:
            print("[警告] benchmark_data 表是空的！")
            return

        print(f"读取到 {len(df)} 条记录")
        print(f"基准代码: {sorted(df['code'].unique())}")
        
        # 确保日期格式统一
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # 确保目录存在
        parquet_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存为 Parquet
        output_path = parquet_dir / 'benchmark_daily.parquet'
        print(f"正在保存到: {output_path}")
        df.to_parquet(output_path, index=False, engine='pyarrow')
        
        # 验证文件
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"[完成] 导出成功！")
        print(f"   文件大小: {file_size_mb:.2f} MB")
        print(f"   记录数: {len(df):,}")
        print(f"   日期范围: {df['date'].min()} ~ {df['date'].max()}")
        
    except Exception as e:
        print(f"[错误] 导出失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    export_benchmark()

