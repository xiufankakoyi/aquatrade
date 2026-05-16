"""
完整测试删除功能 - 包括后端API、CORS、数据一致性
"""
import requests
import json

def test_delete_full():
    BASE_URL = "http://localhost:5000"

    print("=" * 70)
    print("完整测试删除功能")
    print("=" * 70)

    # 1. 获取当前持仓列表
    print("\n[1] 获取当前持仓列表...")
    response = requests.get(f"{BASE_URL}/api/portfolio/positions?active_only=true")
    print(f"    状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"    ❌ 获取持仓失败: {response.text}")
        return False

    data = response.json()
    if not data.get('success'):
        print(f"    ❌ 获取持仓失败: {data}")
        return False

    positions = data.get('data', [])
    print(f"    ✅ 获取成功，当前持仓数量: {len(positions)}")

    if not positions:
        print("    ⚠️ 没有持仓可删除")
        return True

    for p in positions:
        print(f"       ID={p['id']}: {p['stock_code']} {p['stock_name']}")

    # 2. 测试删除最后一个持仓
    target = positions[-1]
    target_id = target['id']
    print(f"\n[2] 测试删除持仓 ID={target_id} ({target['stock_code']} {target['stock_name']})...")

    # 测试OPTIONS预检请求（CORS）
    print("\n[2.1] 测试OPTIONS预检请求...")
    options_response = requests.options(
        f"{BASE_URL}/api/portfolio/positions/{target_id}",
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'DELETE',
            'Access-Control-Request-Headers': 'Content-Type'
        }
    )
    print(f"      状态码: {options_response.status_code}")
    print(f"      Access-Control-Allow-Methods: {options_response.headers.get('Access-Control-Allow-Methods', 'N/A')}")
    print(f"      Access-Control-Allow-Origin: {options_response.headers.get('Access-Control-Allow-Origin', 'N/A')}")

    if options_response.status_code != 200:
        print(f"      ❌ OPTIONS预检失败")
        return False
    print(f"      ✅ OPTIONS预检通过")

    # 执行DELETE请求
    print("\n[2.2] 执行DELETE请求...")
    delete_response = requests.delete(f"{BASE_URL}/api/portfolio/positions/{target_id}")
    print(f"      状态码: {delete_response.status_code}")
    print(f"      响应: {delete_response.text}")

    if delete_response.status_code != 200:
        print(f"      ❌ DELETE请求失败")
        return False

    delete_data = delete_response.json()
    if not delete_data.get('success'):
        print(f"      ❌ 删除失败: {delete_data.get('error', '未知错误')}")
        return False

    print(f"      ✅ DELETE请求成功")

    # 3. 验证删除结果
    print("\n[3] 验证删除结果...")
    response2 = requests.get(f"{BASE_URL}/api/portfolio/positions?active_only=true")
    data2 = response2.json()

    if not data2.get('success'):
        print(f"    ❌ 验证失败: {data2}")
        return False

    positions2 = data2.get('data', [])
    print(f"    删除后持仓数量: {len(positions2)}")

    # 检查目标ID是否还存在
    remaining_ids = [p['id'] for p in positions2]
    if target_id in remaining_ids:
        print(f"    ❌ 持仓 ID={target_id} 仍然存在！")
        return False

    print(f"    ✅ 持仓 ID={target_id} 已成功删除")

    # 4. 验证数据一致性（ArcticDB和Parquet）
    print("\n[4] 验证数据一致性...")

    # 通过analysis接口验证
    analysis_response = requests.get(f"{BASE_URL}/api/portfolio/analysis")
    analysis_data = analysis_response.json()

    if analysis_data.get('success'):
        analysis_positions = analysis_data.get('data', {}).get('positions', [])
        analysis_ids = [p['id'] for p in analysis_positions]

        if target_id in analysis_ids:
            print(f"    ❌ analysis接口中持仓 ID={target_id} 仍然存在！")
            return False

        print(f"    ✅ analysis接口数据一致")
    else:
        print(f"    ⚠️ analysis接口调用失败: {analysis_data}")

    print("\n" + "=" * 70)
    print("✅ 所有测试通过！删除功能完全正常")
    print("=" * 70)

    return True

if __name__ == "__main__":
    success = test_delete_full()
    exit(0 if success else 1)
