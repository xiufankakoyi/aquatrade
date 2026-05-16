#!/usr/bin/env python3
"""
直接测试 Socket.IO 服务器的事件发送
"""
import asyncio
import socketio
from aiohttp import web
import threading
import time

# 创建 Socket.IO 服务器
sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
app = web.Application()
sio.attach(app)

connected_clients = {}

@sio.event
async def connect(sid, environ):
    print(f"[SERVER] 客户端连接: {sid}")
    connected_clients[sid] = True

@sio.event
async def disconnect(sid):
    print(f"[SERVER] 客户端断开: {sid}")
    connected_clients.pop(sid, None)

@sio.on('run_streaming_backtest')
async def handle_backtest(sid, data):
    print(f"[SERVER] 收到回测请求: {data}")
    
    # 发送 backtest_start
    print(f"[SERVER] 发送 backtest_start")
    await sio.emit('backtest_start', {'initialCapital': 1000000}, room=sid)
    
    # 等待一下
    await asyncio.sleep(1)
    
    # 发送 daily_equity 事件
    for i in range(5):
        print(f"[SERVER] 发送 daily_equity #{i+1}")
        await sio.emit('daily_equity', {
            'date': f'2024-05-{20+i}',
            'strategyReturn': 1000000 + i * 10000,
            'benchmarkReturn': 1000000
        }, room=sid)
        await asyncio.sleep(0.5)
    
    # 发送 stream_complete
    print(f"[SERVER] 发送 stream_complete")
    await sio.emit('stream_complete', {'message': '完成'}, room=sid)
    print(f"[SERVER] 所有事件发送完成")

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 5001)
    await site.start()
    print("[SERVER] 服务器启动在 http://localhost:5001")
    
    # 保持运行
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
