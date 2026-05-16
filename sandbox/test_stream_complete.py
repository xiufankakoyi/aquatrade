"""
测试 stream_complete 数据处理
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.binary_packer import pack_backtest_result
import base64

# 模拟 stream_complete 数据
stream_complete_data = {
    'finalEquity': 1000000.0,
    'totalReturn': 0.0,
    'totalTrades': 0,
    'winRate': 0.0,
    'profitFactor': 0.0,
    'equityCurve': [
        {'date': '2024-05-20', 'equity': 1000000.0},
        {'date': '2024-05-21', 'equity': 1000000.0},
        {'date': '2024-05-22', 'equity': 1000000.0},
        {'date': '2024-05-23', 'equity': 1000000.0},
        {'date': '2024-05-24', 'equity': 1000000.0}
    ],
    'trades': []
}

print("=== 测试 stream_complete 数据打包 ===")
try:
    packed = pack_backtest_result(stream_complete_data)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试空数据
print("\n=== 测试空数据 ===")
try:
    packed = pack_backtest_result({})
    print(f"✅ 空字典打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ 空字典打包失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 None
print("\n=== 测试 None ===")
try:
    packed = pack_backtest_result(None)
    print(f"✅ None 打包成功! 大小: {len(packed)} bytes")
except Exception as e:
    print(f"❌ None 打包失败: {e}")
    import traceback
    traceback.print_exc()
