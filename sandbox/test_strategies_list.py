"""
测试脚本：检查策略列表 API
"""

import requests
import json

def test_strategies_list():
    """测试策略列表 API"""
    url = 'http://localhost:5000/api/strategies'

    print(f"[测试] 发送 HTTP GET 请求: {url}")

    try:
        response = requests.get(url, timeout=30)
        print(f"[测试] 响应状态码: {response.status_code}")
        print(f"[测试] 响应内容:")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if isinstance(data, list):
            print(f"[测试] 策略数量: {len(data)}")
            for strategy in data:
                print(f"  - {strategy.get('id', 'N/A')}: {strategy.get('name', 'N/A')}")

    except Exception as e:
        print(f"[测试] 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_strategies_list()
