"""
测试脚本：检查 K 线图数据加载问题
访问 http://localhost:5173/strategy/simple_volume_v3 并检查 K 线图数据
"""

import asyncio
import socketio
import json

async def test_kline_data():
    """测试 K 线数据接口"""
    sio = socketio.AsyncClient()

    @sio.event
    async def connect():
        print("[测试] Socket.IO 已连接")

    @sio.event
    async def disconnect():
        print("[测试] Socket.IO 已断开")

    @sio.on('kline_data')
    async def on_kline_data(data):
        print("[测试] 收到 kline_data 响应:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    try:
        # 连接到后端
        await sio.connect('http://localhost:5000')
        print("[测试] 已连接到 http://localhost:5000")

        # 发送 K 线数据请求
        request_data = {
            'request_id': 'test_kline_12345',
            'symbol_code': '603020',
            'start_date': '2026-01-11',
            'end_date': '2026-02-15'
        }
        print(f"[测试] 发送 request_kline 请求: {request_data}")
        await sio.emit('request_kline', request_data)

        # 等待响应
        await asyncio.sleep(3)

        # 断开连接
        await sio.disconnect()
        print("[测试] 测试完成")

    except Exception as e:
        print(f"[测试] 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_kline_data())
