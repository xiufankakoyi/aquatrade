"""
测试飞书 OCR API - 带长时间等待
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config.config import Config


def get_token(app_id, app_secret):
    """获取 tenant_access_token"""
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    
    old_http_proxy = os.environ.get('HTTP_PROXY')
    old_https_proxy = os.environ.get('HTTPS_PROXY')
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    
    try:
        token_resp = requests.post(
            token_url,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        )
        token_data = token_resp.json()
        
        if token_data.get('code') != 0:
            print(f"获取 token 失败: {token_data}")
            return None
        
        return token_data.get('tenant_access_token')
    finally:
        if old_http_proxy:
            os.environ['HTTP_PROXY'] = old_http_proxy
        if old_https_proxy:
            os.environ['HTTPS_PROXY'] = old_https_proxy


def call_ocr(token, image_key):
    """调用 OCR API"""
    ocr_url = "https://open.feishu.cn/open-apis/optical_char_recognition/v1/image/basic_recognize"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {"image": image_key}
    
    old_http_proxy = os.environ.get('HTTP_PROXY')
    old_https_proxy = os.environ.get('HTTPS_PROXY')
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    
    try:
        resp = requests.post(ocr_url, headers=headers, json=data, timeout=30)
        
        limit = resp.headers.get('x-ogw-ratelimit-limit')
        reset = resp.headers.get('x-ogw-ratelimit-reset')
        
        result = resp.json()
        
        return {
            'status_code': resp.status_code,
            'limit': limit,
            'reset': reset,
            'code': result.get('code'),
            'msg': result.get('msg'),
            'data': result.get('data'),
        }
    finally:
        if old_http_proxy:
            os.environ['HTTP_PROXY'] = old_http_proxy
        if old_https_proxy:
            os.environ['HTTPS_PROXY'] = old_https_proxy


def test_ocr_api():
    """测试 OCR API 并打印限流信息"""
    
    app_id = Config.FEISHU_APP_ID
    app_secret = Config.FEISHU_APP_SECRET
    
    if not app_id or not app_secret:
        print("错误: FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置")
        return False
    
    print(f"App ID: {app_id[:10]}...")
    
    print("\n步骤 1: 获取 tenant_access_token...")
    token = get_token(app_id, app_secret)
    if not token:
        return False
    print(f"Token 获取成功: {token[:20]}...")
    
    print("\n步骤 2: 等待 60 秒让限流恢复...")
    for i in range(60, 0, -1):
        print(f"\r倒计时: {i} 秒  ", end="", flush=True)
        time.sleep(1)
    print("\n")
    
    print("步骤 3: 调用 OCR API...")
    result = call_ocr(token, "img_v3_test_123")
    
    print(f"\n响应状态码: {result['status_code']}")
    print(f"限流信息: limit={result['limit']}, reset={result['reset']}s")
    print(f"响应: code={result['code']}, msg={result['msg']}")
    
    if result['code'] == 0:
        print("\n✅ OCR API 调用成功!")
        print(f"识别结果: {result['data']}")
        return True
    elif result['code'] == 99991400:
        print("\n⚠️ 仍然处于限流状态")
        print("注意: 飞书 OCR API 可能有更严格的限流策略")
        print("建议: 稍后再试，或检查飞书开放平台的 API 限流配置")
        return False
    else:
        print(f"\n响应: code={result['code']}, msg={result['msg']}")
        return False


if __name__ == "__main__":
    test_ocr_api()
