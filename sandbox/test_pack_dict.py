"""
测试 pack_backtest_result 处理字典
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.binary_packer import pack_backtest_result
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

# 测试 risk_data 数据
risk_data = {
    'var95': 0.0,
    'var99': 0.0,
    'beta': 0.0,
    'alpha': 0.0
}

print("=== 测试 final_metrics 打包 ===")
try:
    packed = pack_backtest_result(final_metrics)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 测试 risk_data 打包 ===")
try:
    packed = pack_backtest_result(risk_data)
    print(f"✅ 打包成功! 大小: {len(packed)} bytes")
    packed_b64 = base64.b64encode(packed).decode('utf-8')
    print(f"✅ base64 编码成功! 长度: {len(packed_b64)} chars")
except Exception as e:
    print(f"❌ 打包失败: {e}")
    import traceback
    traceback.print_exc()
