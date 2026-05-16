import requests

BASE_URL = "http://localhost:5000"

print("测试CORS响应头...")

# 测试OPTIONS请求
options_response = requests.options(
    f"{BASE_URL}/api/portfolio/positions/1",
    headers={
        'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'DELETE',
        'Access-Control-Request-Headers': 'Content-Type'
    }
)

print(f"\nOPTIONS请求状态码: {options_response.status_code}")
print("响应头:")
for key, value in options_response.headers.items():
    if key.lower().startswith('access-control'):
        print(f"  {key}: {value}")

# 测试实际的DELETE请求
delete_response = requests.delete(
    f"{BASE_URL}/api/portfolio/positions/1",
    headers={'Origin': 'http://localhost:5173'}
)

print(f"\nDELETE请求状态码: {delete_response.status_code}")
print("响应头:")
for key, value in delete_response.headers.items():
    if key.lower().startswith('access-control'):
        print(f"  {key}: {value}")
