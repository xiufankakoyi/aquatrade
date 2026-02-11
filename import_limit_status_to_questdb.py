"""
将 stock_limit_status.parquet 导入 QuestDB
"""
import time
import polars as pl
import psycopg2
from pathlib import Path

# 读取 Parquet 文件
parquet_file = Path('data/parquet_data/stock_limit_status.parquet')
print(f'读取 Parquet 文件: {parquet_file}')

df = pl.scan_parquet(str(parquet_file)).collect()
print(f'总行数: {len(df):,}')

# 连接到 QuestDB
conn = psycopg2.connect(
    host='localhost',
    port=8812,
    database='qdb',
    user='admin',
    password='quest'
)
cursor = conn.cursor()

# 创建表 - 使用 designated timestamp
# 先将 trade_date 转换为 timestamp
cursor.execute('''
CREATE TABLE IF NOT EXISTS stock_limit_status (
    stock_code SYMBOL,
    trade_date TIMESTAMP,
    is_limit_up LONG,
    is_limit_down LONG,
    is_opened LONG,
    is_suspended LONG
) TIMESTAMP(trade_date) PARTITION BY YEAR;
''')
conn.commit()
print('表创建完成')

# 检查是否已有数据
cursor.execute('SELECT count() FROM stock_limit_status')
count = cursor.fetchone()[0]
print(f'QuestDB 中已有数据: {count:,} 行')

if count > 0:
    print('数据已存在，跳过导入')
else:
    # 转换为 pandas 并插入
    pdf = df.to_pandas()

    # 批量插入
    batch_size = 10000
    total = len(pdf)
    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = pdf.iloc[i:i+batch_size]

        # 构建 INSERT 语句
        values = []
        for _, row in batch.iterrows():
            values.append(f"('{row['stock_code']}', '{row['trade_date']}', {row['is_limit_up']}, {row['is_limit_down']}, {row['is_opened']}, {row['is_suspended']})")

        sql = f"INSERT INTO stock_limit_status VALUES {','.join(values)}"
        cursor.execute(sql)
        conn.commit()

        if (i // batch_size) % 10 == 0:
            elapsed = time.time() - start_time
            progress = i / total * 100
            print(f'  进度: {i:,}/{total:,} ({progress:.1f}%) - 耗时: {elapsed:.1f}s')

    print(f'导入完成，总行数: {total:,}')

cursor.close()
conn.close()
print('Done!')
