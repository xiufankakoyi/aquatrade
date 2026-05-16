"""
检查后端回测错误详情
"""
import requests
import json

# 测试策略列表
print("=== 测试策略列表 API ===")
try:
    resp = requests.get("http://localhost:5000/api/strategies", timeout=5)
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    print(f"策略数量: {len(data.get('data', []))}")
except Exception as e:
    print(f"错误: {e}")

# 测试直接调用回测 API（非流式）
print("\n=== 测试直接回测 API ===")
try:
    payload = {
        "strategy_name": "收敛三角形倒计时策略",
        "start_date": "2024-05-20",
        "end_date": "2024-05-25",
        "benchmark_code": "000300"
    }
    resp = requests.post(
        "http://localhost:5000/api/run_backtest",  # 正确的路由
        json=payload,
        timeout=30
    )
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    if data.get('success'):
        print("回测成功!")
        metrics = data.get('data', {}).get('metrics', {})
        print(f"总收益率: {metrics.get('total_return', 'N/A')}")
        print(f"交易次数: {metrics.get('trades_count', 'N/A')}")
    else:
        print(f"回测失败: {data.get('error', '未知错误')}")
        print(f"完整响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 检查完成 ===")
