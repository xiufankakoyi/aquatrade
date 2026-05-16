"""检查数据中的股票数量和代码格式"""
import sys
sys.path.insert(0, '.')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

query = OptimizedStockDataQuery()
df = query.get_market_data('2025-01-02')

print(f'数据中的股票总数: {len(df)}')
print()

# 统计各板块
code_counts = {
    '沪市主板(600/601/603/605)': 0,
    '科创板(688)': 0,
    '深市主板(000/001/002/003)': 0,
    '创业板(300/301)': 0,
    '北交所(8/9/43/83/87)': 0,
    '其他': 0
}

for code in df['stock_code']:
    if code.startswith('6'):
        code_counts['沪市主板(600/601/603/605)'] += 1
    elif code.startswith('688'):
        code_counts['科创板(688)'] += 1
    elif code.startswith('0'):
        code_counts['深市主板(000/001/002/003)'] += 1
    elif code.startswith('3'):
        code_counts['创业板(300/301)'] += 1
    elif code.startswith(('8', '9', '43', '83', '87')):
        code_counts['北交所(8/9/43/83/87)'] += 1
    else:
        code_counts['其他'] += 1

print('股票分布:')
for k, v in code_counts.items():
    print(f'  {k}: {v}')

print()
print('深市主板股票示例(000开头):')
sz_stocks = df[df['stock_code'].str.startswith('0')]['stock_code'].tolist()
print(sz_stocks[:20])

print()
print('检查聚宽买入的000030是否存在:')
if '30' in df['stock_code'].values:
    print('  30: 存在')
if '000030' in df['stock_code'].values:
    print('  000030: 存在')
if '000030.XSHE' in df['stock_code'].values:
    print('  000030.XSHE: 存在')
