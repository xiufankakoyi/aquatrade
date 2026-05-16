"""
测试脚本：使用 HTTP 请求测试 K 线数据接口
"""

import requests
import json

def test_kline_http():
    """测试 K 线数据 HTTP 接口"""
    url = 'http://localhost:5000/api/visualization/symbol-kline'
    params = {
        'symbol_code': '603020',
        'start_date': '2026-01-11',
        'end_date': '2026-02-15'
    }

    print(f"[测试] 发送 HTTP GET 请求: {url}")
    print(f"[测试] 参数: {params}")

    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"[测试] 响应状态码: {response.status_code}")
        print(f"[测试] 响应内容:")
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if isinstance(data, list):
            print(f"[测试] 数据条数: {len(data)}")
        elif isinstance(data, dict) and 'data' in data:
            print(f"[测试] 数据条数: {len(data['data'])}")

    except Exception as e:
        print(f"[测试] 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_kline_http()
