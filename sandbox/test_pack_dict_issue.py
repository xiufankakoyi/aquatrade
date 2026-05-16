"""
测试 pack_backtest_result 处理字典时的问题
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.binary_packer import pack_backtest_result
import base64

# 测试 final_metrics 数据（字典）
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

print("=== 测试 final_metrics 打包 ===")
try:
    packed = pack_backtest_result(final_metrics)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
    
    # 测试解码
    import msgpack
    unpacked = msgpack.unpackb(base64.b64decode(packed_b64), raw=False)
    print(f"✅ 解码成功! 数据: {unpacked}")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试空字典
print("\n=== 测试空字典 ===")
try:
    packed = pack_backtest_result({})
    print(f"✅ 空字典打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ 空字典打包失败: {e}")

# 测试 None
print("\n=== 测试 None ===")
try:
    packed = pack_backtest_result(None)
    print(f"✅ None 打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ None 打包失败: {e}")
