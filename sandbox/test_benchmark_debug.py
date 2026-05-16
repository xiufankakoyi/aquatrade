"""
测试基准数据调试
"""
import requests
import time

def test_benchmark_debug():
    print("=" * 80)
    print("测试基准数据调试")
    print("=" * 80)
    
    # 直接调用 API 触发回测
    url = "http://localhost:5000/api/run_backtest"
    params = {
        "strategy_name": "聚宽量比市值策略",
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "benchmark_code": "000300"
    }
    
    print(f"\n[1] 发送回测请求: {params}")
    
    try:
        response = requests.post(url, json=params, timeout=120)
        print(f"\n[2] 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n[3] 完整响应:")
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
            
            # 检查基准曲线
            benchmark_curve = result.get('benchmarkCurve', [])
            print(f"\n[4] 基准曲线:")
            print(f"  点数: {len(benchmark_curve)}")
            if benchmark_curve:
                print(f"  前3个: {benchmark_curve[:3]}")
                print(f"  后3个: {benchmark_curve[-3:]}")
                
                # 检查跳跃
                changes = []
                for i in range(1, len(benchmark_curve)):
                    prev_val = benchmark_curve[i-1]['equity']
                    curr_val = benchmark_curve[i]['equity']
                    change = (curr_val - prev_val) / prev_val * 100
                    changes.append(change)
                    if abs(change) > 2:
                        print(f"  [WARN] 大跳跃: {benchmark_curve[i-1]['date']} -> {benchmark_curve[i]['date']}, 变化 {change:.2f}%")
                
                print(f"\n  日变化统计:")
                print(f"    最大涨幅: {max(changes):.2f}%")
                print(f"    最大跌幅: {min(changes):.2f}%")
        else:
            print(f"  错误: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_benchmark_debug()
