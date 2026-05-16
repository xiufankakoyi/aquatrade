"""
测试 partition_by 返回格式
"""
import polars as pl

df = pl.DataFrame({
    'trade_date': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
    'stock_code': ['000001', '000002', '000001', '000002'],
    'close': [10.0, 20.0, 11.0, 21.0],
})

print("原始数据:")
print(df)

print("\npartition_by('trade_date', as_dict=True):")
partitioned = df.partition_by('trade_date', as_dict=True)
for key, val in partitioned.items():
    print(f"  key={key} (type={type(key)}), df={len(val)} 行")

print("\n修正后的遍历:")
for date_key, day_df in partitioned.items():
    if isinstance(date_key, tuple):
        date_str = str(date_key[0])
    else:
        date_str = str(date_key)
    print(f"  date_str={date_str}, df={len(day_df)} 行")
