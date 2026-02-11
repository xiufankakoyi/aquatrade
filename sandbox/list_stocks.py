# list_stocks.py

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import polars as pl

dq = OptimizedStockDataQuery()
# Access internal manager
mgr = dq._lancedb_mgr
df = mgr.load_to_polars("stock_info")
print(f"Total stocks: {len(df)}")
print("Sample symbols:")
print(df.select("stock_code").head(10))

# Try searching for 601988
found = df.filter(pl.col("stock_code").str.contains("601988"))
print("\nSearch for 601988:")
print(found)
