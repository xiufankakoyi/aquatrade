"""
LLM 连通性冒烟测试 (sandbox/test_llm_smoke.py)

测试内容：
1. 配置加载校验
2. 直接 HTTP 探测 /models（最快判断 key 是否有效）
3. 走 AquaLLM 生成一行文本（端到端验证）

运行：
    python sandbox/test_llm_smoke.py
"""

import sys
import traceback
from pathlib import Path

# 把项目根目录加入 sys.path，确保能 import config / core
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from config.config import Config


def check_config():
    """校验关键配置是否就位"""
    missing = []
    for key in ("LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL_NAME"):
        val = getattr(Config, key, None)
        if not val:
            missing.append(key)
        else:
            # 脱敏打印
            masked = val if key != "LLM_API_KEY" else f"{val[:6]}***{val[-4:]}"
            print(f"  [OK] {key} = {masked}")
    if missing:
        print(f"  [FAIL] 缺失配置: {missing}")
        return False
    return True


def http_probe():
    """通过 HTTP 探测 /models 端点，最快判断连通性 + Key 有效性"""
    base = Config.LLM_API_BASE.rstrip("/")
    url = f"{base}/models"
    print(f"\n[1/3] HTTP 探测: GET {url}")
    try:
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {Config.LLM_API_KEY}"},
            timeout=10,
        )
        print(f"  状态码: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, dict) and "data" in data:
                    models = [m.get("id", "?") for m in data["data"][:5]]
                    print(f"  可用模型(前5): {models}")
                else:
                    print(f"  响应: {str(data)[:200]}")
            except Exception:
                print(f"  非 JSON 响应: {r.text[:200]}")
            return True
        else:
            print(f"  响应内容: {r.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"  [FAIL] 网络异常: {e}")
        return False


def aqua_generate():
    """端到端：调用 AquaLLM 生成一行文本"""
    print(f"\n[2/3] 调用 AquaLLM.generate_code() 生成测试代码")
    try:
        from core.utils.llm_client import AquaLLM

        llm = AquaLLM()
        code = llm.generate_code(
            user_prompt="用 Python 写一个 hello world，只输出代码",
        )
        print(f"  返回长度: {len(code)} 字符")
        print(f"  返回前 200 字符:\n----\n{code[:200]}\n----")
        return True
    except Exception as e:
        print(f"  [FAIL] 调用失败: {e}")
        traceback.print_exc()
        return False


def aqua_stream():
    """流式输出一句话，验证 stream 通道"""
    print(f"\n[3/3] 调用 AquaLLM.generate_report_stream() 流式输出")
    try:
        from core.utils.llm_client import AquaLLM

        llm = AquaLLM()
        parts = []
        for chunk in llm.generate_report_stream(
            user_prompt="用一句话介绍你自己，不要超过30字",
        ):
            print(chunk, end="", flush=True)
            parts.append(chunk)
        print()
        text = "".join(parts).strip()
        if text.startswith("[ERROR]"):
            print(f"  [FAIL] 流式返回错误: {text}")
            return False
        print(f"\n  流式累计 {len(text)} 字符")
        return True
    except Exception as e:
        print(f"  [FAIL] 流式调用失败: {e}")
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("LLM 冒烟测试")
    print("=" * 60)

    print("\n[0/3] 配置加载")
    if not check_config():
        sys.exit(1)

    results = {
        "http_probe": http_probe(),
        "aqua_generate": aqua_generate(),
        "aqua_stream": aqua_stream(),
    }

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")

    if all(results.values()):
        print("\nLLM 可用 ✅")
        sys.exit(0)
    else:
        print("\nLLM 存在异常 ❌，请检查 base_url / api_key / 模型名")
        sys.exit(1)


if __name__ == "__main__":
    main()
