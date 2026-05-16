"""测试 get_market_data 方法"""
import sys
sys.path.insert(0, '.')

from data_svc.database.optimized_data_query import OptimizedStockDataQuery

query = OptimizedStockDataQuery()
df = query.get_market_data('2025-01-02')

print(f'get_market_data 返回的股票数: {len(df)}')
print(f'列名: {df.columns.tolist()}')
print()

# 检查 stock_code 列
if 'stock_code' in df.columns:
    codes = df['stock_code'].unique().tolist()
    print(f'唯一股票数: {len(codes)}')
    print(f'stock_code 示例: {codes[:20]}')
    print()
    
    # 统计各板块
    sz_count = sum(1 for c in codes if str(c).startswith('0'))
    cyb_count = sum(1 for c in codes if str(c).startswith('3'))
    sh_count = sum(1 for c in codes if str(c).startswith('6'))
    kcb_count = sum(1 for c in codes if str(c).startswith('688'))
    
    print(f'沪市主板(6开头): {sh_count}')
    print(f'科创板(688): {kcb_count}')
    print(f'深市主板(0开头): {sz_count}')
    print(f'创业板(3开头): {cyb_count}')
    print()
    
    # 检查聚宽买入的股票
    print('检查聚宽买入的股票:')
    target_stocks = ['000030', '002626', '002403']
    for code in target_stocks:
        found = code in codes
        print(f'  {code}: {"存在" if found else "不存在"}')
