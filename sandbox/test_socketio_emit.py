"""
测试 Socket.IO emit 是否能正常工作
"""
import sys
import os
import asyncio

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 测试 stream_complete 数据
stream_complete_data = {
    'finalEquity': 1000000.0,
    'totalReturn': 0.0,
    'totalTrades': 0,
    'winRate': 0.0,
    'profitFactor': 0.0,
    'equityCurve': [
        {'date': '2024-05-20', 'equity': 1000000.0},
        {'date': '2024-05-21', 'equity': 1000000.0},
    ],
    'trades': []
}

print("=== 测试数据 ===")
print(f"数据类型: {type(stream_complete_data)}")
print(f"数据内容: {stream_complete_data}")

# 测试数据序列化
import json
print("\n=== 测试 JSON 序列化 ===")
try:
    json_str = json.dumps(stream_complete_data)
    print(f"✅ JSON 序列化成功! 长度: {len(json_str)} chars")
except Exception as e:
    print(f"❌ JSON 序列化失败: {e}")

# 测试 MsgPack 序列化
print("\n=== 测试 MsgPack 序列化 ===")
try:
    from utils.binary_packer import pack_backtest_result
    import base64
    packed = pack_backtest_result(stream_complete_data)
    print(f"✅ MsgPack 序列化成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ MsgPack 序列化失败: {e}")

print("\n=== 所有测试完成 ===")
