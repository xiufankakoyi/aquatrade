"""检查聚宽买入股票的市值"""
import sys
sys.path.insert(0, '.')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

query = OptimizedStockDataQuery()
df = query.get_market_data('2025-01-02')

# 聚宽买入的股票
target_stocks = ['000030', '002626', '002403', '600511', '600755']

print('聚宽买入的股票市值:')
for code in target_stocks:
    # 尝试不同格式
    matches = df[df['stock_code'].str.contains(code, na=False)]
    if not matches.empty:
        row = matches.iloc[0]
        mv = row['total_mv']  # 单位：十万元
        stock_code = row['stock_code']
        print(f'  {stock_code}: {mv:.0f} 十万元 = {mv/10000:.2f} 亿元')
    else:
        print(f'  {code}: 未找到')

print()
print('你的策略买入的股票市值 (前10只):')
your_stocks = ['000423', '000538', '000063', '000034', '000338', 
               '000157', '000541', '000506', '000581', '000501']
for code in your_stocks:
    matches = df[df['stock_code'].str.contains(code, na=False)]
    if not matches.empty:
        row = matches.iloc[0]
        mv = row['total_mv']
        stock_code = row['stock_code']
        print(f'  {stock_code}: {mv:.0f} 十万元 = {mv/10000:.2f} 亿元')
    else:
        print(f'  {code}: 未找到')
