"""
测试持仓分析API返回的数据
"""
import requests

def test_api():
    print("测试持仓分析API...")
    
    url = "http://localhost:5000/api/portfolio/analysis"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            positions = data['data'].get('positions', [])
            print(f"\n持仓数量: {len(positions)}")
            
            for p in positions:
                print(f"\n{p['stock_code']} - {p['stock_name']}")
                print(f"  买入价: {p.get('buy_price')}")
                print(f"  现价: {p.get('current_price')}")
                print(f"  盈亏: {p.get('profit_loss')} ({p.get('profit_loss_pct')}%)")
                
                if '中概' in p['stock_name']:
                    print("  ^^^ 中概互联ETF ^^^")
        else:
            print(f"API错误: {data.get('error')}")
    else:
        print(f"请求失败: {response.status_code}")

if __name__ == "__main__":
    test_api()
