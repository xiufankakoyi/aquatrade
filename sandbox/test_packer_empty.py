"""
测试 pack_backtest_result 函数处理空列表
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.binary_packer import pack_backtest_result, MSGPACK_AVAILABLE

# 测试空列表
test_data_empty = []

# 测试有数据的列表
test_data_with_data = [
    {'date': '2024-05-20', 'strategyReturn': 1000000.0, 'benchmarkReturn': 1000000.0},
]

print(f"MsgPack 可用: {MSGPACK_AVAILABLE}")

print("\n=== 测试空列表 ===")
try:
    packed = pack_backtest_result(test_data_empty)
    print(f"✅ 空列表打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ 空列表打包失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试有数据的列表 ===")
try:
    packed = pack_backtest_result(test_data_with_data)
    print(f"✅ 有数据列表打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ 有数据列表打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 base64 编码
print("\n=== 测试 base64 编码 ===")
import base64
try:
    packed = pack_backtest_result(test_data_with_data)
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ base64 编码失败: {e}")
    import traceback
    traceback.print_exc()
