"""
测试脚本：检查多个策略的详情 API
"""

import requests
import json

def test_strategy_detail(strategy_id):
    """测试策略详情 API"""
    url = f'http://localhost:5000/api/strategy/{strategy_id}'

    print(f"\n[测试] 策略: {strategy_id}")
    print(f"[测试] 发送 HTTP GET 请求: {url}")

    try:
        response = requests.get(url, timeout=30)
        print(f"[测试] 响应状态码: {response.status_code}")
        data = response.json()

        if 'trades' in data:
            print(f"[测试] 交易记录数量: {len(data['trades'])}")
        else:
            print("[测试] 响应中没有 'trades' 字段")

        if 'equityCurve' in data:
            print(f"[测试] 权益曲线数据点: {len(data['equityCurve'])}")

        if 'metrics' in data:
            print(f"[测试] 指标: {data['metrics']}")

        return len(data.get('trades', [])) > 0

    except Exception as e:
        print(f"[测试] 错误: {e}")
        return False

if __name__ == '__main__':
    strategies = [
        'simple_volume_v3',
        'simple_volume_v5',
        'optimized_volume_v1',
        'jq_volume_v1',
        'jq_volume_v1pro',
        'dual_ma_v1',
    ]

    for strategy_id in strategies:
        has_data = test_strategy_detail(strategy_id)
        if has_data:
            print(f"[测试] ✓ 策略 {strategy_id} 有数据")
            break
    else:
        print("\n[测试] 所有策略都没有回测数据")
