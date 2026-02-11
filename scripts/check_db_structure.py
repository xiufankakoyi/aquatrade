import sqlite3

# 连接数据库
conn = sqlite3.connect('d:/aquatrade/data_svc/database/stock_data.db')
cursor = conn.cursor()

# 查看 backtest_results 表结构
print('backtest_results表结构:')
cursor.execute('PRAGMA table_info(backtest_results)')
for row in cursor.fetchall():
    print(row)

# 查看 trade_records 表结构
print('\ntrade_records表结构:')
cursor.execute('PRAGMA table_info(trade_records)')
for row in cursor.fetchall():
    print(row)

# 关闭连接
conn.close()