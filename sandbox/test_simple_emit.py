#!/usr/bin/env python3
"""
简单测试 Socket.IO 事件发送
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

@sio.event
async def connect(sid, environ):
    print(f"[SERVER] 客户端连接: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[SERVER] 客户端断开: {sid}")

@sio.on('test_emit')
async def handle_test(sid, data):
    print(f"[SERVER] 收到测试请求: {data}")
    
    main_loop = asyncio.get_event_loop()
    
    # 在后台线程中发送事件
    def send_events():
        print("[THREAD] 开始发送事件")
        
        # 使用 run_coroutine_threadsafe
        for i in range(5):
            event_name = 'test_event'
            payload = {'index': i, 'message': f'事件 {i}'}
            
            async def do_emit(name=event_name, data=payload):
                await sio.emit(name, data, room=sid)
                print(f"[EMIT] 已发送 {name}: {data}")
            
            asyncio.run_coroutine_threadsafe(do_emit(), main_loop)
            print(f"[THREAD] 已提交事件 {i}")
            time.sleep(0.5)
        
        print("[THREAD] 所有事件已提交")
    
    # 在后台线程中运行
    await main_loop.run_in_executor(None, send_events)
    print("[SERVER] 后台线程完成")

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 5002)
    await site.start()
    print("[SERVER] 服务器启动在 http://localhost:5002")
    
    # 保持运行
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
