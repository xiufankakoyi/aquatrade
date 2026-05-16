"""
测试后端接口是否正常工作
"""
import requests

def test_backend():
    print("测试后端接口...")

    url = "http://localhost:5000/api/screener/field_stats"
    payload = {
        "field": "rsi_6",
        "date": "2026-02-13"
    }

    try:
        response = requests.post(url, json=payload)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")
    except Exception as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    test_backend()
