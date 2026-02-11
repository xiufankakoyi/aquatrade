"""
使用 ILP (InfluxDB Line Protocol) 将 stock_limit_status 导入 QuestDB
速度比 SQL INSERT 快 10-100 倍
"""
import time
import socket
import polars as pl
from pathlib import Path
from datetime import datetime

# 读取 Parquet 文件
parquet_file = Path('data/parquet_data/stock_limit_status.parquet')
print(f'读取 Parquet 文件: {parquet_file}')

df = pl.scan_parquet(str(parquet_file)).collect()
print(f'总行数: {len(df):,}')

# 转换为 ILP 格式
# 格式: table_name,symbols fields timestamp
print('构建 ILP 数据...')
ilp_lines = []

for row in df.iter_rows(named=True):
    stock_code = row['stock_code']
    trade_date = row['trade_date']  # '2024-04-01'
    is_limit_up = row['is_limit_up']
    is_limit_down = row['is_limit_down']
    is_opened = row['is_opened']
    is_suspended = row['is_suspended']
    
    # 将日期字符串转换为 Unix 时间戳（毫秒）
    ts = int(time.mktime(time.strptime(trade_date, '%Y-%m-%d'))) * 1000
    
    # ILP 格式: stock_limit_status,stock_code=xxx is_limit_up=x,is_limit_down=x,is_opened=x,is_suspended=x timestamp
    ilp_line = f'stock_limit_status,stock_code={stock_code} is_limit_up={is_limit_up}i,is_limit_down={is_limit_down}i,is_opened={is_opened}i,is_suspended={is_suspended}i {ts}'
    ilp_lines.append(ilp_line)

print(f'ILP 行数: {len(ilp_lines):,}')

# 通过 TCP 发送到 QuestDB ILP 端口 (9009)
print('连接到 QuestDB ILP 端口...')
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)
sock.connect(('localhost', 9009))

# 分批发送
batch_size = 5000
total = len(ilp_lines)
start_time = time.time()

for i in range(0, total, batch_size):
    batch = ilp_lines[i:i+batch_size]
    data = '\n'.join(batch) + '\n'
    sock.sendall(data.encode())
    
    if (i // batch_size) % 20 == 0:
        elapsed = time.time() - start_time
        progress = i / total * 100
        rate = i / elapsed if elapsed > 0 else 0
        print(f'  进度: {i:,}/{total:,} ({progress:.1f}%) - 耗时: {elapsed:.1f}s - 速率: {rate:.0f} 行/秒')

sock.close()
print(f'导入完成！总耗时: {time.time() - start_time:.1f}s')
