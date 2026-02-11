"""
QuestDB 数据导入脚本 (PostgreSQL 协议)
========================================
使用 PostgreSQL Wire Protocol 高效导入大批量数据。

用法:
    python scripts/import_to_questdb_pg.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
import psycopg2
from datetime import datetime

# QuestDB 配置
QUESTDB_HOST = "localhost"
QUESTDB_PG_PORT = 8812

# 热数据文件路径
BASE_DIR = r"d:\aquatrade\data\parquet_data"
FILES = {
    "base": os.path.join(BASE_DIR, "base_daily_hot.parquet"),
    "momentum": os.path.join(BASE_DIR, "factors_momentum_hot.parquet"),
    "valuation": os.path.join(BASE_DIR, "factors_valuation_hot.parquet"),
}


def create_tables(conn):
    """创建表结构"""
    cursor = conn.cursor()
    
    ddls = [
        """
        CREATE TABLE IF NOT EXISTS base_daily (
            ts TIMESTAMP,
            code SYMBOL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume LONG,
            amount DOUBLE,
            adj_factor DOUBLE,
            prev_close DOUBLE
        ) TIMESTAMP(ts) PARTITION BY MONTH;
        """,
        """
        CREATE TABLE IF NOT EXISTS factors_momentum (
            ts TIMESTAMP,
            code SYMBOL,
            rsi_14 DOUBLE,
            kdj_k DOUBLE,
            kdj_d DOUBLE,
            kdj_j DOUBLE,
            macd_dif DOUBLE,
            macd_dea DOUBLE,
            macd_histogram DOUBLE,
            atr_14 DOUBLE,
            ma5 DOUBLE,
            ma10 DOUBLE,
            ma20 DOUBLE,
            ma60 DOUBLE,
            ma120 DOUBLE,
            ma250 DOUBLE,
            boll_upper DOUBLE,
            boll_mid DOUBLE,
            boll_lower DOUBLE,
            bias_5 DOUBLE,
            bias_10 DOUBLE,
            bias_20 DOUBLE
        ) TIMESTAMP(ts) PARTITION BY MONTH;
        """,
        """
        CREATE TABLE IF NOT EXISTS factors_valuation (
            ts TIMESTAMP,
            code SYMBOL,
            pe DOUBLE,
            pe_ttm DOUBLE,
            pb DOUBLE,
            ps DOUBLE,
            ps_ttm DOUBLE,
            total_mv DOUBLE,
            float_mv DOUBLE,
            turnover_rate DOUBLE,
            turnover_free DOUBLE,
            volume_ratio DOUBLE,
            dividend_yield DOUBLE
        ) TIMESTAMP(ts) PARTITION BY MONTH;
        """
    ]
    
    for ddl in ddls:
        try:
            cursor.execute(ddl)
            conn.commit()
        except Exception as e:
            print(f"   ⚠️ DDL 警告: {e}")
            conn.rollback()
    
    cursor.close()


def insert_batch(conn, table_name: str, df: pl.DataFrame, batch_size: int = 10000):
    """
    批量插入数据
    """
    cursor = conn.cursor()
    total = len(df)
    
    # 获取列名
    columns = df.columns
    placeholders = ",".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
    
    for i in range(0, total, batch_size):
        batch = df.slice(i, batch_size)
        
        # 转换为 Python 原生类型的 list of tuples
        rows = []
        for row_dict in batch.iter_rows(named=True):
            row = tuple(row_dict[col] for col in columns)
            rows.append(row)
        
        try:
            cursor.executemany(insert_sql, rows)
            conn.commit()
        except Exception as e:
            print(f"\n      ⚠️ 批次 {i//batch_size + 1} 失败: {str(e)[:80]}")
            conn.rollback()
        
        progress = min(100, (i + batch_size) * 100 // total)
        print(f"      进度: {progress}%", end="\r")
    
    print()
    cursor.close()


def main():
    print("=" * 60)
    print("📊 QuestDB 数据导入工具 (PostgreSQL)")
    print("=" * 60)
    
    # 1. 连接 QuestDB
    print("\n[1/5] 连接 QuestDB...")
    try:
        conn = psycopg2.connect(
            host=QUESTDB_HOST,
            port=QUESTDB_PG_PORT,
            user="admin",
            password="quest",
            database="qdb"
        )
        print("   ✓ 连接成功")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("   请确保 QuestDB 正在运行")
        return False
    
    # 2. 创建表
    print("\n[2/5] 创建表结构...")
    create_tables(conn)
    print("   ✓ 表结构已就绪")
    
    # 3-5: 导入数据
    print("\n[3/5] 导入 base_daily...")
    base_df = pl.read_parquet(FILES["base"])
    base_df = base_df.select([
        pl.col("trade_date").str.strptime(pl.Datetime, "%Y-%m-%d").alias("ts"),
        pl.col("stock_code").alias("code"),
        "open", "high", "low", "close", "volume", "amount", "adj_factor", "prev_close"
    ])
    print(f"   读取 {len(base_df):,} 行")
    start_time = datetime.now()
    insert_batch(conn, "base_daily", base_df)
    print(f"   ✓ 完成 ({(datetime.now() - start_time).total_seconds():.1f}s)")
    
    print("\n[4/5] 导入 factors_momentum...")
    momentum_df = pl.read_parquet(FILES["momentum"])
    momentum_df = momentum_df.select([
        pl.col("trade_date").str.strptime(pl.Datetime, "%Y-%m-%d").alias("ts"),
        pl.col("stock_code").alias("code"),
        "rsi_14", "kdj_k", "kdj_d", "kdj_j",
        "macd_dif", "macd_dea", "macd_histogram", "atr_14",
        "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
        "boll_upper", "boll_mid", "boll_lower",
        "bias_5", "bias_10", "bias_20"
    ])
    print(f"   读取 {len(momentum_df):,} 行")
    start_time = datetime.now()
    insert_batch(conn, "factors_momentum", momentum_df)
    print(f"   ✓ 完成 ({(datetime.now() - start_time).total_seconds():.1f}s)")
    
    print("\n[5/5] 导入 factors_valuation...")
    valuation_df = pl.read_parquet(FILES["valuation"])
    valuation_df = valuation_df.select([
        pl.col("trade_date").str.strptime(pl.Datetime, "%Y-%m-%d").alias("ts"),
        pl.col("stock_code").alias("code"),
        "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "total_mv", "float_mv", "turnover_rate", "turnover_free",
        "volume_ratio", "dividend_yield"
    ])
    print(f"   读取 {len(valuation_df):,} 行")
    start_time = datetime.now()
    insert_batch(conn, "factors_valuation", valuation_df)
    print(f"   ✓ 完成 ({(datetime.now() - start_time).total_seconds():.1f}s)")
    
    # 验证
    print("\n[验证] 检查导入结果...")
    cursor = conn.cursor()
    for table in ["base_daily", "factors_momentum", "factors_valuation"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count:,} 行")
    cursor.close()
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ 数据导入完成!")
    print("=" * 60)
    print(f"\n访问 QuestDB Web UI: http://localhost:9000")
    print("\n示例查询:")
    print("  SELECT code, ts, close FROM base_daily LIMIT 10;")
    print("  SELECT code, rsi_14 FROM factors_momentum WHERE rsi_14 < 30;")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
