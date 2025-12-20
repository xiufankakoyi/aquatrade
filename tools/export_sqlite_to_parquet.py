import os
import sqlite3

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DB_PATH = "database/stock_data.db"
EXPORT_DIR = "parquet_data"

os.makedirs(EXPORT_DIR, exist_ok=True)


def export_table_chunked(table_name: str, chunksize: int = 500_000):
    """
    从 SQLite 按块读取一个表，并写成单个 Parquet 文件。
    - 以第一块推断统一 schema，后续所有块按这个 schema 转，
      避免某些列全空时被推成 null 类型导致 schema 不一致。
    """
    out_path = os.path.join(EXPORT_DIR, f"{table_name}.parquet")
    print(f"Exporting {table_name} -> {out_path}")
    conn = sqlite3.connect(DB_PATH)
    if not table_exists(conn, table_name):
        print(f"- skip: table {table_name} does not exist in {DB_PATH}")
        conn.close()
        return
    # 如果之前有半成品，先删掉
    if os.path.exists(out_path):
        os.remove(out_path)
        print(f"- removed existing file: {out_path}")


    # 先拿一块确定 schema
    first_chunk_iter = pd.read_sql_query(
        f"SELECT * FROM {table_name}",
        conn,
        chunksize=chunksize,
    )

    try:
        first_chunk = next(first_chunk_iter)
    except StopIteration:
        print(f"- Table {table_name} is empty, skip.")
        conn.close()
        return

    # 用第一块推断统一的 Arrow schema
    first_table = pa.Table.from_pandas(first_chunk, preserve_index=False)
    schema = first_table.schema

    writer = pq.ParquetWriter(out_path, schema, compression="zstd")

    # 写第一块（按统一 schema 转）
    writer.write_table(pa.Table.from_pandas(first_chunk, schema=schema, preserve_index=False))
    print(f"- wrote first chunk: {len(first_chunk)} rows")

    # 写剩下的块（全部按统一 schema 转）
    total_rows = len(first_chunk)
    for i, chunk in enumerate(first_chunk_iter, start=2):
        table = pa.Table.from_pandas(chunk, schema=schema, preserve_index=False)
        writer.write_table(table)
        total_rows += len(chunk)
        print(f"- wrote chunk {i}: {len(chunk)} rows (total={total_rows})")

    writer.close()
    conn.close()
    print(f"Done {table_name}, total {total_rows} rows.\n")
def table_exists(conn, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    )
    return cur.fetchone() is not None



if __name__ == "__main__":
    export_table_chunked("stock_daily")
    export_table_chunked("stock_info")
    #export_table_chunked("adjustment_factors")
    print("All exported!")
