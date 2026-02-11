import requests
import os
import pandas as pd
from questdb.ingress import Sender
from datetime import datetime

QUESTDB_HOST = "localhost"
QUESTDB_HTTP_PORT = 9000
QUESTDB_ILP_PORT = 9009
QUESTDB_HOST_ENV = os.getenv("QUESTDB_HOST", "localhost")

TABLE_NAME = "factors_valuation"
PARQUET_FILE = r"d:\aquatrade\data\parquet_data\factors_valuation_hot.parquet"

DDL = """
CREATE TABLE factors_valuation (
    trade_date TIMESTAMP,
    stock_code SYMBOL,
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
) TIMESTAMP(trade_date) PARTITION BY MONTH BYPASS WAL;
"""

def drop_and_create_table():
    print(f"Dropping table {TABLE_NAME}...")
    try:
        # Drop
        requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": f"DROP TABLE {TABLE_NAME}"})
        
        # Create
        print(f"Creating table {TABLE_NAME} (BYPASS WAL)...")
        r = requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": DDL})
        if r.status_code == 200:
            print(f"✅ Created {TABLE_NAME}: {r.json().get('ddl')}")
        else:
            print(f"⚠️ Failed to create {TABLE_NAME}: {r.text}")
            raise Exception("Create failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise e

def _prepare_dataframe(df: pd.DataFrame, ts_col: str = "trade_date") -> pd.DataFrame:
    if ts_col not in df.columns:
        raise KeyError(f"时间列 `{ts_col}` 不存在，请检查 Parquet 文件结构")
    df[ts_col] = pd.to_datetime(df[ts_col])
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str)
    return df

def import_table(chunk_size: int = 5000):
    print(f"\n=== 正在导入表 `{TABLE_NAME}` ===")
    print(f"读取文件: {PARQUET_FILE}")
    df = pd.read_parquet(PARQUET_FILE, engine="pyarrow")
    # Rename columns to match DDL if necessary, but DDL uses 'stock_code' and parquet uses 'stock_code' usually.
    # Check parquet columns
    print(f"Columns: {df.columns.tolist()}")
    
    df = _prepare_dataframe(df, ts_col="trade_date")
    
    total_rows = len(df)
    print(f"总行数: {total_rows:,}, 分批大小: {chunk_size:,}")

    with Sender('tcp', QUESTDB_HOST_ENV, QUESTDB_ILP_PORT) as sender:
        for i in range(0, total_rows, chunk_size):
            chunk = df.iloc[i : i + chunk_size]
            try:
                sender.dataframe(
                    chunk,
                    table_name=TABLE_NAME,
                    at="trade_date",
                )
                sender.flush()
                print(f"  ✅ 批次 {i // chunk_size + 1} 成功 ({len(chunk):,} 行) - 进度: {min(100, (i + chunk_size) / total_rows * 100):.1f}%", end="\r")
            except Exception as e:
                print(f"\n  ❌ 批次 {i // chunk_size + 1} 失败: {e}")
                raise e
    print(f"\n✅ 表 `{TABLE_NAME}` 导入完成")

if __name__ == "__main__":
    drop_and_create_table()
    import_table()
