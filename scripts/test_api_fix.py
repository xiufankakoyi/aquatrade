import requests

# 测试策略详情API
strategy_name = "聚宽量比市值策略pro"
url = f"http://localhost:5000/api/strategy/{strategy_name}"

try:
    response = requests.get(url, timeout=5)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"交易记录数量: {len(data['trades'])}")
        print(f"回测指标: {data['metrics']}")
        
        # 打印前几条交易记录
        if data['trades']:
            print("\n前5条交易记录:")
            for trade in data['trades'][:5]:
                print(f"ID: {trade['id']}, 日期: {trade['date']}, 股票: {trade['symbol']}, 操作: {trade['action']}, 价格: {trade['price']}, 盈亏: {trade['profitLoss']}")
    else:
        print(f"请求失败: {response.text}")
except Exception as e:
    print(f"请求出错: {e}")