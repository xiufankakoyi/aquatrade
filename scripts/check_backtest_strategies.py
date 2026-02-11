import sqlite3

# 连接数据库
conn = sqlite3.connect('d:/aquatrade/data_svc/database/stock_data.db')
cursor = conn.cursor()

# 查询所有策略名称
print('数据库中的策略名称:')
cursor.execute('SELECT DISTINCT strategy_name FROM backtest_results')
for row in cursor.fetchall():
    print(row[0])

# 查询所有回测结果
print('\n所有回测结果:')
cursor.execute('SELECT id, strategy_name, start_date, end_date, trade_count, created_at FROM backtest_results')
for row in cursor.fetchall():
    print(row)

# 关闭连接
conn.close()