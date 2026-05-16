"""
导入持仓历史数据 - 直接使用 Parquet 存储
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import os
from datetime import datetime

# 股票名称到代码映射
STOCK_MAP = {
    '生益科技': ('600183', 'SH'),
    '通富微电': ('002156', 'SZ'),
    '中概互联': ('513050', 'SH'),
    '中国长城': ('000066', 'SZ'),
    '宏和科技': ('603256', 'SH'),
    '中国移动': ('600941', 'SH'),
    '桐昆股份': ('601233', 'SH'),
    '中金黄金': ('600489', 'SH'),
    '上峰水泥': ('000672', 'SZ'),
    '思源电气': ('002028', 'SZ'),
    '洁美科技': ('002859', 'SZ'),
    '新洁能': ('605111', 'SH'),
    '招商轮船': ('601872', 'SH'),
    '东方锆业': ('002167', 'SZ'),
    '中航西飞': ('000768', 'SZ'),
    '雪迪龙': ('002658', 'SZ'),
    '黄河旋风': ('600172', 'SH'),
    '意华股份': ('002897', 'SZ'),
}

TRADES = '''生益科技 买入 69.140 300 2026-02-25
通富微电 买入 50.010 600 2026-02-25
通富微电 买入 49.620 400 2026-02-25
中概互联 卖出 1.346 72800 2026-02-25
通富微电 买入 50.470 200 2026-02-25
中国长城 卖出 16.520 1000 2026-02-24
中国长城 卖出 16.440 800 2026-02-24
宏和科技 卖出 76.230 200 2026-02-24
中国移动 卖出 92.897 300 2026-02-24
宏和科技 卖出 77.400 500 2026-02-24
桐昆股份 买入 24.090 1100 2026-02-25
中金黄金 买入 31.460 700 2026-02-25
桐昆股份 卖出 24.340 1100 2026-02-27
桐昆股份 卖出 24.190 1000 2026-02-27
上峰水泥 卖出 14.960 1600 2026-02-27
通富微电 卖出 52.110 1200 2026-02-26
生益科技 卖出 73.013 300 2026-02-26
上峰水泥 买入 15.020 1600 2026-02-26
桐昆股份 买入 23.990 1000 2026-02-26
桐昆股份 买入 24.150 500 2026-02-26
思源电气 卖出 225.710 100 2026-02-26
通富微电 买入 51.870 300 2026-02-27
洁美科技 买入 42.190 200 2026-02-27
新洁能 买入 47.280 200 2026-02-27
桐昆股份 买入 24.080 700 2026-02-27
通富微电 买入 52.010 300 2026-02-27
新洁能 买入 47.410 300 2026-02-27
洁美科技 买入 42.160 400 2026-02-27
招商轮船 买入 15.790 600 2026-02-27
洁美科技 买入 42.340 200 2026-02-27
桐昆股份 买入 24.010 600 2026-02-27
东方锆业 买入 15.510 1600 2026-03-02
中航西飞 买入 31.100 800 2026-03-02
通富微电 买入 51.100 400 2026-03-02
桐昆股份 卖出 24.370 1300 2026-03-02
招商轮船 卖出 16.837 600 2026-03-02
通富微电 买入 51.460 500 2026-03-02
新洁能 卖出 47.260 500 2026-03-02
雪迪龙 买入 11.160 2200 2026-03-02
洁美科技 卖出 43.220 400 2026-03-02
黄河旋风 买入 9.300 1000 2026-03-02
意华股份 买入 65.740 200 2026-03-03
意华股份 买入 65.740 200 2026-03-03
中航西飞 卖出 29.460 200 2026-03-03
中航西飞 卖出 29.460 600 2026-03-03
黄河旋风 卖出 9.650 1000 2026-03-03
意华股份 买入 66.200 200 2026-03-03
意华股份 买入 66.210 200 2026-03-03
中金黄金 卖出 34.500 700 2026-03-03
黄河旋风 买入 9.360 1300 2026-03-03'''

def parse_trades(text):
    records = []
    for line in text.strip().split('\n'):
        parts = line.strip().split()
        if len(parts) >= 5:
            name = parts[0]
            action = parts[1]
            price = float(parts[2])
            shares = int(parts[3])
            date = parts[4]
            records.append({
                'name': name,
                'action': action,
                'price': price,
                'shares': shares,
                'date': date
            })
    return records

def main():
    records = parse_trades(TRADES)
    print(f'共 {len(records)} 条交易记录')
    
    records.sort(key=lambda x: x['date'])
    
    positions = {}
    
    for r in records:
        name = r['name']
        if name not in STOCK_MAP:
            print(f'未找到股票: {name}')
            continue
        
        code, market = STOCK_MAP[name]
        action = r['action']
        price = r['price']
        shares = r['shares']
        date = r['date']
        amount = price * shares
        
        if action == '买入':
            if code not in positions:
                positions[code] = {
                    'code': code,
                    'market': market,
                    'name': name,
                    'shares': 0,
                    'cost': 0,
                    'first_buy_date': date
                }
            positions[code]['shares'] += shares
            positions[code]['cost'] += amount
        elif action == '卖出':
            if code in positions:
                cost_per_share = positions[code]['cost'] / positions[code]['shares'] if positions[code]['shares'] > 0 else 0
                positions[code]['shares'] -= shares
                positions[code]['cost'] -= cost_per_share * shares
                if positions[code]['shares'] <= 0:
                    del positions[code]
    
    print(f'\n当前持仓: {len(positions)} 只')
    
    now = datetime.now().isoformat()
    
    rows = []
    for i, (code, pos) in enumerate(positions.items(), 1):
        avg_price = pos['cost'] / pos['shares'] if pos['shares'] > 0 else 0
        print(f"  {pos['name']} ({code}): {pos['shares']}股, 成本{pos['cost']:.2f}, 均价{avg_price:.3f}")
        
        rows.append({
            'id': i,
            'stock_code': code,
            'stock_name': pos['name'],
            'buy_price': avg_price,
            'shares': pos['shares'],
            'cost': pos['cost'],
            'buy_date': pos['first_buy_date'],
            'stop_loss': None,
            'take_profit': None,
            'notes': '',
            'is_active': 1,
            'created_at': now,
            'updated_at': now
        })
    
    df = pd.DataFrame(rows)
    
    from config.config import Config
    parquet_path = os.path.join(Config.PARQUET_DIR, 'portfolio_positions.parquet')
    os.makedirs(Config.PARQUET_DIR, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    
    print(f'\n已保存到: {parquet_path}')
    print('导入完成!')

if __name__ == '__main__':
    main()
