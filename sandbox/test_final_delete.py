"""
最终完整测试 - 测试整个删除流程
"""
import requests
import json

def test_complete_workflow():
    BASE_URL = "http://localhost:5000"

    print("=" * 70)
    print("最终完整测试 - 删除持仓工作流")
    print("=" * 70)

    # 1. 先添加一个测试持仓
    print("\n[1] 添加测试持仓...")
    add_data = {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "buy_price": 10.5,
        "shares": 1000,
        "cost": 10500,
        "buy_date": "2026-02-17",
        "is_active": True
    }

    add_response = requests.post(f"{BASE_URL}/api/portfolio/positions", json=add_data)
    print(f"    状态码: {add_response.status_code}")

    if add_response.status_code != 200:
        print(f"    ❌ 添加失败: {add_response.text}")
        return False

    add_result = add_response.json()
    if not add_result.get('success'):
        print(f"    ❌ 添加失败: {add_result}")
        return False

    new_id = add_result.get('data', {}).get('id')
    print(f"    ✅ 添加成功，新持仓ID: {new_id}")

    # 2. 验证持仓已添加
    print(f"\n[2] 验证持仓已添加...")
    get_response = requests.get(f"{BASE_URL}/api/portfolio/positions?active_only=true")
    get_data = get_response.json()

    if not get_data.get('success'):
        print(f"    ❌ 获取失败: {get_data}")
        return False

    positions = get_data.get('data', [])
    ids = [p['id'] for p in positions]

    if new_id not in ids:
        print(f"    ❌ 新持仓不存在！")
        return False

    print(f"    ✅ 持仓已添加，当前持仓数: {len(positions)}")

    # 3. 测试CORS预检
    print(f"\n[3] 测试CORS预检请求...")
    options_response = requests.options(
        f"{BASE_URL}/api/portfolio/positions/{new_id}",
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'DELETE',
            'Access-Control-Request-Headers': 'Content-Type'
        }
    )

    if options_response.status_code != 200:
        print(f"    ❌ CORS预检失败: {options_response.status_code}")
        return False

    allow_methods = options_response.headers.get('Access-Control-Allow-Methods', '')
    if 'DELETE' not in allow_methods:
        print(f"    ❌ CORS未允许DELETE方法: {allow_methods}")
        return False

    print(f"    ✅ CORS预检通过，允许方法: {allow_methods}")

    # 4. 执行删除
    print(f"\n[4] 执行删除请求...")
    delete_response = requests.delete(f"{BASE_URL}/api/portfolio/positions/{new_id}")
    print(f"    状态码: {delete_response.status_code}")
    print(f"    响应: {delete_response.text}")

    if delete_response.status_code != 200:
        print(f"    ❌ 删除请求失败")
        return False

    delete_data = delete_response.json()
    if not delete_data.get('success'):
        print(f"    ❌ 删除失败: {delete_data.get('error')}")
        return False

    print(f"    ✅ 删除请求成功")

    # 5. 验证删除结果
    print(f"\n[5] 验证删除结果...")
    verify_response = requests.get(f"{BASE_URL}/api/portfolio/positions?active_only=true")
    verify_data = verify_response.json()

    if not verify_data.get('success'):
        print(f"    ❌ 验证失败: {verify_data}")
        return False

    positions_after = verify_data.get('data', [])
    ids_after = [p['id'] for p in positions_after]

    if new_id in ids_after:
        print(f"    ❌ 持仓仍然存在！")
        return False

    print(f"    ✅ 持仓已删除，当前持仓数: {len(positions_after)}")

    # 6. 验证analysis接口一致性
    print(f"\n[6] 验证analysis接口一致性...")
    analysis_response = requests.get(f"{BASE_URL}/api/portfolio/analysis")
    analysis_data = analysis_response.json()

    if not analysis_data.get('success'):
        print(f"    ❌ analysis接口失败: {analysis_data}")
        return False

    analysis_positions = analysis_data.get('data', {}).get('positions', [])
    analysis_ids = [p['id'] for p in analysis_positions]

    if new_id in analysis_ids:
        print(f"    ❌ analysis接口中持仓仍然存在！")
        return False

    print(f"    ✅ analysis接口数据一致")

    print("\n" + "=" * 70)
    print("✅ 所有测试通过！删除功能完全正常")
    print("=" * 70)

    return True

if __name__ == "__main__":
    success = test_complete_workflow()
    exit(0 if success else 1)
