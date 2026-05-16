"""
测试 pack_backtest_result 函数
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.binary_packer import pack_backtest_result, MSGPACK_AVAILABLE

# 模拟回测数据
test_data = [
    {'date': '2024-05-20', 'strategyReturn': 1000000.0, 'benchmarkReturn': 1000000.0},
    {'date': '2024-05-21', 'strategyReturn': 1000000.0, 'benchmarkReturn': 995989.88},
    {'date': '2024-05-22', 'strategyReturn': 1000000.0, 'benchmarkReturn': 998235.88},
    {'date': '2024-05-23', 'strategyReturn': 1000000.0, 'benchmarkReturn': 986678.11},
    {'date': '2024-05-24', 'strategyReturn': 1000000.0, 'benchmarkReturn': 975755.13},
]

print(f"MsgPack 可用: {MSGPACK_AVAILABLE}")
print(f"测试数据: {test_data}")

try:
    packed = pack_backtest_result(test_data)
    print(f"\n✅ 打包成功!")
    print(f"打包后大小: {len(packed)} bytes")
    
    # 验证可以解包
    import msgpack
    unpacked = msgpack.unpackb(packed, raw=False)
    print(f"解包后数据长度: {len(unpacked)}")
    print(f"第一条数据: {unpacked[0]}")
    
except Exception as e:
    print(f"\n❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()
