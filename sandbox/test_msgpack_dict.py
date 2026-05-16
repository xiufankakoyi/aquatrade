"""
测试 msgpack.packb 处理字典
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import msgpack
import base64

# 测试 final_metrics 数据
final_metrics = {
    'totalReturn': 0.0,
    'annualizedReturn': 0.0,
    'maxDrawdown': 0.0,
    'sharpeRatio': 0.0,
    'volatility': 0.0,
    'winRate': 0.0,
    'profitFactor': 0.0,
    'totalTrades': 0
}

print("=== 测试 msgpack.packb 处理 final_metrics ===")
try:
    packed = msgpack.packb(final_metrics, use_bin_type=True, strict_types=False)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 risk_data 数据
risk_data = {
    'var95': 0.0,
    'var99': 0.0,
    'beta': 0.0,
    'alpha': 0.0
}

print("\n=== 测试 msgpack.packb 处理 risk_data ===")
try:
    packed = msgpack.packb(risk_data, use_bin_type=True, strict_types=False)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试空字典
print("\n=== 测试 msgpack.packb 处理空字典 ===")
try:
    packed = msgpack.packb({}, use_bin_type=True, strict_types=False)
    print(f"✅ 空字典打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ 空字典打包失败: {e}")

# 测试 None
print("\n=== 测试 msgpack.packb 处理 None ===")
try:
    packed = msgpack.packb(None, use_bin_type=True, strict_types=False)
    print(f"✅ None 打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ None 打包失败: {e}")

print("\n=== 所有测试完成 ===")
