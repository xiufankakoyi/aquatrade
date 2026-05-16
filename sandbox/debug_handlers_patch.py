"""
调试补丁：找出 [Errno 22] Invalid argument 的来源
"""
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 模拟 Socket.IO 环境
class MockSocketIO:
    async def emit(self, event, data, room=None):
        print(f"[MockSocketIO.emit] {event}: {type(data)}")
        # 检查数据类型
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {type(value)} = {value if not isinstance(value, str) or len(value) < 100 else value[:100] + '...'}")

# 测试 pack_backtest_result 和 base64 编码
from utils.binary_packer import pack_backtest_result
import base64

# 模拟回测数据
buffers = {
    'daily_equity': [
        {'date': '2024-05-20', 'strategyReturn': 1000000.0, 'benchmarkReturn': 1000000.0},
        {'date': '2024-05-21', 'strategyReturn': 1000000.0, 'benchmarkReturn': 995989.88},
    ],
    'new_trade': [],
    'signal': []
}

sio = MockSocketIO()

def flush_buffers():
    """刷新所有缓冲池，发送积攒的消息"""
    event_name_map = {
        'daily_equity': 'daily_equity',
        'new_trade': 'new_trade',
        'signal': 'signal'
    }
    
    for event_type, buffer in buffers.items():
        if buffer:
            try:
                print(f"\n[flush_buffers] 处理 {event_type}, 缓冲大小: {len(buffer)}")
                
                # 确保 buffer 是列表且每个元素都是字典
                if isinstance(buffer, list) and all(isinstance(item, dict) for item in buffer):
                    packed = pack_backtest_result(buffer)
                    print(f"  打包后大小: {len(packed)} bytes")
                    
                    # 将 bytes 转换为 base64 字符串
                    packed_b64 = base64.b64encode(packed).decode('utf-8')
                    print(f"  base64 编码后长度: {len(packed_b64)} chars")
                    
                    frontend_event = event_name_map.get(event_type, event_type)
                    print(f"  发送事件: {frontend_event}")
                    
                    # 模拟发送
                    import asyncio
                    asyncio.run(sio.emit(frontend_event, {
                        '_msgpack': True,
                        '_data': packed_b64,
                        '_count': len(buffer),
                        '_batch': True
                    }))
                else:
                    print(f"  数据结构不符合预期: {type(buffer)}")
                    
                buffer.clear()
                print(f"  缓冲已清空")
            except Exception as e:
                print(f"❌ 发送批量消息失败 ({event_type}): {e}")
                import traceback
                traceback.print_exc()

print("=== 测试 flush_buffers ===")
try:
    flush_buffers()
    print("\n✅ flush_buffers 成功")
except Exception as e:
    print(f"\n❌ flush_buffers 失败: {e}")
    import traceback
    traceback.print_exc()
