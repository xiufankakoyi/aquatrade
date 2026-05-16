"""
测试 fund_updater.py 的频率限制修复
"""
import sys
import os

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.database.fund_updater import (
    call_with_rate_limit,
    reset_rate_limit,
    get_rate_limit,
    RATE_LIMITS
)


def test_rate_limit_config():
    """测试频率限制配置"""
    print("=" * 60)
    print("测试频率限制配置")
    print("=" * 60)

    for api_name, limit in RATE_LIMITS.items():
        assert get_rate_limit(api_name) == limit, f"{api_name} 配置错误"
        print(f"  {api_name}: {limit} 次/分钟")

    print("\n✓ 频率限制配置测试通过")


def test_reset_rate_limit():
    """测试重置频率限制功能"""
    print("\n" + "=" * 60)
    print("测试重置频率限制功能")
    print("=" * 60)

    # 重置所有
    reset_rate_limit()
    print("  ✓ 重置所有频率限制计数器")

    # 重置指定 API
    reset_rate_limit('fund_nav')
    print("  ✓ 重置 fund_nav 频率限制计数器")

    print("\n✓ 重置功能测试通过")


def test_call_with_rate_limit():
    """测试带频率限制的 API 调用"""
    print("\n" + "=" * 60)
    print("测试带频率限制的 API 调用")
    print("=" * 60)

    # 模拟 API 调用
    def mock_api_call(*args, **kwargs):
        return {"status": "ok", "args": args, "kwargs": kwargs}

    # 测试不同 API 的调用
    for api_name in ['fund_nav', 'fund_div', 'fund_basic']:
        result = call_with_rate_limit(mock_api_call, api_name=api_name)
        assert result["status"] == "ok"
        print(f"  ✓ {api_name} 调用成功")

    print("\n✓ API 调用测试通过")


def main():
    print("\n" + "=" * 60)
    print("fund_updater.py 频率限制修复测试")
    print("=" * 60 + "\n")

    try:
        test_rate_limit_config()
        test_reset_rate_limit()
        test_call_with_rate_limit()

        print("\n" + "=" * 60)
        print("所有测试通过！频率限制修复成功。")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
