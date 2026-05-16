#!/usr/bin/env python3
"""
简单测试 Socket.IO 客户端
"""
import socketio
import time

sio = socketio.Client()

@sio.event
def connect():
    print('[CLIENT] 已连接')
    sio.emit('test_emit', {'message': '开始测试'})

@sio.event
def disconnect():
    print('[CLIENT] 断开连接')

@sio.on('test_event')
def on_test_event(data):
    print(f'[CLIENT] 收到事件: {data}')

print('[CLIENT] 连接服务器...')
sio.connect('http://localhost:5002')

print('[CLIENT] 等待事件...')
time.sleep(5)

print('[CLIENT] 断开连接')
sio.disconnect()
