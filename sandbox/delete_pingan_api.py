"""
通过 API 删除所有平安银行持仓
"""
import requests
import time

BASE_URL = 'http://localhost:5000'

def delete_all_pingan_positions():
    while True:
        # 1. 获取当前持仓
        print("获取当前持仓...")
        resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
        
        if not resp.json().get('success'):
            print(f"获取持仓失败: {resp.json()}")
            break
        
        positions = resp.json()['data']
        
        # 2. 找到平安银行的持仓
        pingan_positions = [p for p in positions if '平安银行' in p.get('stock_name', '')]
        
        if not pingan_positions:
            print("✅ 没有找到平安银行持仓，删除完成！")
            break
        
        print(f"找到 {len(pingan_positions)} 条平安银行持仓:")
        for p in pingan_positions:
            print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")
        
        # 3. 删除第一条
        first = pingan_positions[0]
        print(f"\n删除 ID={first['id']}...")
        
        del_resp = requests.delete(f"{BASE_URL}/api/portfolio/positions/{first['id']}")
        print(f"删除响应: {del_resp.json()}")
        
        if not del_resp.json().get('success'):
            print(f"删除失败: {del_resp.json()}")
            break
        
        print("删除成功！\n")
        time.sleep(0.5)
    
    # 最终验证
    print("\n=== 最终验证 ===")
    resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
    positions = resp.json()['data']
    print(f"当前持仓数量: {len(positions)}")
    for p in positions:
        print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")

if __name__ == "__main__":
    delete_all_pingan_positions()
