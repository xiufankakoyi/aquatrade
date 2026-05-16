"""
删除所有平安银行持仓
"""
import requests
import time

BASE_URL = 'http://localhost:5000'

def delete_all_pingan():
    while True:
        resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
        positions = resp.json().get('data', [])
        
        pingan = [p for p in positions if '平安银行' in p.get('stock_name', '')]
        
        if not pingan:
            print("✅ 所有平安银行持仓已删除！")
            break
        
        target = pingan[0]
        print(f"删除 ID={target['id']}: {target['stock_name']}")
        
        del_resp = requests.delete(f"{BASE_URL}/api/portfolio/positions/{target['id']}")
        print(f"  结果: {del_resp.json()}")
        
        time.sleep(0.3)
    
    # 最终验证
    resp = requests.get(f'{BASE_URL}/api/portfolio/positions?active_only=false')
    positions = resp.json().get('data', [])
    print(f"\n剩余持仓数量: {len(positions)}")
    for p in positions:
        print(f"  ID={p['id']}: {p['stock_code']} {p['stock_name']}")

if __name__ == "__main__":
    delete_all_pingan()
