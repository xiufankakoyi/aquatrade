"""
QuestDB ILP 导入脚本
--------------------
读取本地 Parquet（热数据）并通过 ILP（InfluxDB Line Protocol）高速写入 QuestDB。

使用方式：
    python d:\\aquatrade\\scripts\\import_parquet_ilp.py
"""

import os
import pandas as pd
from questdb.ingress import Sender
from datetime import datetime

# ------------------- 配置 -------------------
QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", "9009"))   # ILP 写入端口

# Parquet 文件所在目录（相对项目根目录）
BASE_DIR = r"d:\\aquatrade\\data\\parquet_data"

# 表名 ↔︎ 文件映射
TABLES = {
    "base_daily": os.path.join(BASE_DIR, "base_daily_hot.parquet"),
    "factors_momentum": os.path.join(BASE_DIR, "factors_momentum_hot.parquet"),
    "factors_valuation": os.path.join(BASE_DIR, "factors_valuation_hot.parquet"),
}
# ------------------------------------------------

def _prepare_dataframe(df: pd.DataFrame, ts_col: str = "trade_date") -> pd.DataFrame:
    """确保时间列为 datetime64[ns]，并把所有 object 列转为字符串。"""
    if ts_col not in df.columns:
        raise KeyError(f"时间列 `{ts_col}` 不存在，请检查 Parquet 文件结构")
    df[ts_col] = pd.to_datetime(df[ts_col])
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str)
    return df

def import_table(table_name: str, parquet_path: str, chunk_size: int = 5000):
    print(f"\n=== 正在导入表 `{table_name}` ===")
    print(f"读取文件: {parquet_path}")
    df = pd.read_parquet(parquet_path, engine="pyarrow")
    df = _prepare_dataframe(df, ts_col="trade_date")
    
    total_rows = len(df)
    print(f"总行数: {total_rows:,}, 分批大小: {chunk_size:,}")

    with Sender('tcp', QUESTDB_HOST, QUESTDB_ILP_PORT) as sender:
        for i in range(0, total_rows, chunk_size):
            chunk = df.iloc[i : i + chunk_size]
            try:
                sender.dataframe(
                    chunk,
                    table_name=table_name,
                    at="trade_date",
                )
                sender.flush()  # Explicit flush after each chunk
                print(f"  ✅ 批次 {i // chunk_size + 1} 成功 ({len(chunk):,} 行) - 进度: {min(100, (i + chunk_size) / total_rows * 100):.1f}%", end="\r")
            except Exception as e:
                print(f"\n  ❌ 批次 {i // chunk_size + 1} 失败: {e}")
                raise e
    print(f"\n✅ 表 `{table_name}` 导入完成")

def main():
    start = datetime.now()
    print("=== QuestDB ILP 导入脚本启动 ===")
    print(f"目标 QuestDB: {QUESTDB_HOST}:{QUESTDB_ILP_PORT}")
    for tbl, path in TABLES.items():
        if not os.path.exists(path):
            print(f"⚠️ 文件不存在: {path}，跳过 `{tbl}`")
            continue
        try:
            import_table(tbl, path)
        except Exception as e:
            print(f"❌ 导入 `{tbl}` 失败: {e}")
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n=== 全部导入结束，耗时 {elapsed:.1f}s ===")

if __name__ == "__main__":
    main()
