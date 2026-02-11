"""
QuestDB 数据导入脚本 (HTTP CSV 方式)
======================================
使用 QuestDB 的 HTTP CSV 导入接口，更稳定可靠。

用法:
    python scripts/import_to_questdb_csv.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
import requests
from io import StringIO
from datetime import datetime

# QuestDB 配置
QUESTDB_HOST = "localhost"
QUESTDB_HTTP_PORT = 9000

# 热数据文件路径
BASE_DIR = r"d:\aquatrade\data\parquet_data"
FILES = {
    "base": os.path.join(BASE_DIR, "base_daily_hot.parquet"),
    "momentum": os.path.join(BASE_DIR, "factors_momentum_hot.parquet"),
    "valuation": os.path.join(BASE_DIR, "factors_valuation_hot.parquet"),
}


def import_via_csv(table_name: str, df: pl.DataFrame, batch_size: int = 100000):
    """
    通过 HTTP CSV 接口导入数据到 QuestDB
    
    Args:
        table_name: 表名
        df: Polars DataFrame
        batch_size: 每批数据行数
    """
    total = len(df)
    url = f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/imp"
    
    for i in range(0, total, batch_size):
        batch = df.slice(i, batch_size)
        
        # 转换为 CSV 字符串
        csv_buffer = StringIO()
        batch.write_csv(csv_buffer)
        csv_data = csv_buffer.getvalue()
        
        # HTTP POST 上传
        response = requests.post(
            url,
            files={"data": (f"{table_name}.csv", csv_data, "text/csv")},
            data={
                "name": table_name,
                "overwrite": "false",  # 追加模式
                "timestamp": "ts",      # 指定时间戳列
                "partitionBy": "MONTH"
            }
        )
        
        if response.status_code != 200:
            print(f"      ⚠️ 批次 {i//batch_size + 1} 失败: {response.text[:100]}")
        
        progress = min(100, (i + batch_size) * 100 // total)
        print(f"      进度: {progress}%", end="\r")
    
    print()  # 换行


def main():
    print("=" * 60)
    print("📊 QuestDB 数据导入工具 (HTTP CSV)")
    print("=" * 60)
    
    # 1. 检查 QuestDB 连接
    print("\n[1/5] 检查 QuestDB 连接...")
    try:
        resp = requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": "SELECT 1"}, timeout=5)
        if resp.status_code != 200:
            print("❌ QuestDB 未运行")
            return False
        print("   ✓ QuestDB 运行正常")
    except:
        print("❌ 无法连接到 QuestDB")
        print("   请先运行: start_questdb.bat")
        return False
    
    # 2. 创建表结构
    print("\n[2/5] 创建表结构...")
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
        requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": ddl.strip()})
    print("   ✓ 表结构已就绪")
    
    # 3. 准备数据格式
    print("\n[3/5] 准备基础行情数据...")
    base_df = pl.read_parquet(FILES["base"])
    
    # 重命名列并选择需要的字段
    base_df = base_df.select([
        pl.col("trade_date").alias("ts"),
        pl.col("stock_code").alias("code"),
        "open", "high", "low", "close", "volume", "amount", "adj_factor", "prev_close"
    ])
    print(f"   读取 {len(base_df):,} 行")
    
    # 4. 导入数据
    print("\n[4/5] 导入所有表...")
    
    start_time = datetime.now()
    print("   [4.1] 导入 base_daily...")
    import_via_csv("base_daily", base_df)
    
    print("   [4.2] 导入 factors_momentum...")
    momentum_df = pl.read_parquet(FILES["momentum"])
    momentum_df = momentum_df.select([
        pl.col("trade_date").alias("ts"),
        pl.col("stock_code").alias("code"),
        "rsi_14", "kdj_k", "kdj_d", "kdj_j",
        "macd_dif", "macd_dea", "macd_histogram", "atr_14",
        "ma5", "ma10", "ma20", "ma60", "ma120", "ma250",
        "boll_upper", "boll_mid", "boll_lower",
        "bias_5", "bias_10", "bias_20"
    ])
    import_via_csv("factors_momentum", momentum_df)
    
    print("   [4.3] 导入 factors_valuation...")
    valuation_df = pl.read_parquet(FILES["valuation"])
    valuation_df = valuation_df.select([
        pl.col("trade_date").alias("ts"),
        pl.col("stock_code").alias("code"),
        "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "total_mv", "float_mv", "turnover_rate", "turnover_free",
        "volume_ratio", "dividend_yield"
    ])
    import_via_csv("factors_valuation", valuation_df)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # 5. 验证
    print(f"\n[5/5] 验证导入结果...")
    for table in ["base_daily", "factors_momentum", "factors_valuation"]:
        resp = requests.get(
            f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec",
            params={"query": f"SELECT COUNT(*) FROM {table}"}
        )
        if resp.status_code == 200:
            data = resp.json()
            count = data["dataset"][0][0] if data.get("dataset") else 0
            print(f"   {table}: {count:,} 行")
    
    print("\n" + "=" * 60)
    print(f"✅ 数据导入完成! 耗时: {elapsed:.1f}s")
    print("=" * 60)
    print(f"\n访问 QuestDB Web UI: http://localhost:9000")
    print("\n示例查询:")
    print("  SELECT code, ts, close FROM base_daily LIMIT 10;")
    print("  SELECT code, rsi_14 FROM factors_momentum WHERE rsi_14 < 30;")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
