import logging
import sys
import pandas as pd
from questdb.ingress import Sender
import requests

QUESTDB_HOST = "localhost"
QUESTDB_ILP_PORT = 9009
QUESTDB_HTTP_PORT = 9000

def drop_table(table_name):
    print(f"Dropping table {table_name}...")
    try:
        r = requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": f"DROP TABLE {table_name}"})
        print(f"Drop result: {r.text}")
    except Exception as e:
        print(f"Drop failed: {e}")

def test_import_small():
    table_name = "base_daily"
    parquet_path = r"d:\aquatrade\data\parquet_data\base_daily_hot.parquet"
    
    print(f"Reading 100 rows from {parquet_path}...")
    df = pd.read_parquet(parquet_path, engine="pyarrow").head(100)
    
    # Validation/Prep
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str)
        
    print(f"Attempting to insert 100 rows via ILP...")
    try:
        with Sender('tcp', QUESTDB_HOST, QUESTDB_ILP_PORT) as sender:
            sender.dataframe(df, table_name=table_name, at="trade_date")
            sender.flush()
        print("✅ Small batch success!")
    except Exception as e:
        print(f"❌ Small batch failed: {e}")

if __name__ == "__main__":
    drop_table("base_daily")
    test_import_small()
