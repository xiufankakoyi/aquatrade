"""
测试脚本：检查策略详情 API
"""

import requests
import json

def test_strategy_api():
    """测试策略详情 API"""
    url = 'http://localhost:5000/api/strategy/simple_volume_v3'

    print(f"[测试] 发送 HTTP GET 请求: {url}")

    try:
        response = requests.get(url, timeout=30)
        print(f"[测试] 响应状态码: {response.status_code}")
        print(f"[测试] 响应内容:")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if 'trades' in data:
            print(f"[测试] 交易记录数量: {len(data['trades'])}")
        else:
            print("[测试] 响应中没有 'trades' 字段")

    except Exception as e:
        print(f"[测试] 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_strategy_api()
