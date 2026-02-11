import sqlite3

# 连接数据库
conn = sqlite3.connect('d:/aquatrade/data_svc/database/stock_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 测试策略名称
strategy_name = "聚宽量比市值策略pro"

# 执行与API相同的查询
print(f"查询策略: {strategy_name}")

# 查询该策略的最新回测结果
cursor.execute('''
    SELECT * FROM backtest_results 
    WHERE strategy_name = ? 
    ORDER BY created_at DESC 
    LIMIT 1
''', (strategy_name,))

backtest_result = cursor.fetchone()

if backtest_result:
    print(f"找到回测结果: ID={backtest_result['id']}, 交易次数={backtest_result['trade_count']}")
    
    # 查询对应的交易记录数量
    cursor.execute('''
        SELECT COUNT(*) FROM trade_records 
        WHERE backtest_id = ?
    ''', (backtest_result['id'],))
    
    trade_count = cursor.fetchone()[0]
    print(f"交易记录数量: {trade_count}")
    
    # 查询前几条交易记录
    cursor.execute('''
        SELECT * FROM trade_records 
        WHERE backtest_id = ? 
        ORDER BY date ASC
        LIMIT 5
    ''', (backtest_result['id'],))
    
    trade_records = cursor.fetchall()
    
    print("前5条交易记录:")
    for record in trade_records:
        print(f"ID: {record['id']}, 日期: {record['date']}, 股票: {record['stock_code']}, 操作: {record['action']}, 价格: {record['price']}, 盈亏: {record['profit_loss']}")
else:
    print("未找到回测结果")

# 关闭连接
conn.close()