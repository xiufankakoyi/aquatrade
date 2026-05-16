"""
测试 Socket.IO 进度推送
"""
import requests
import time
import socketio

sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print('[Socket.IO] 已连接')

@sio.on('db_update_progress')
def on_progress(data):
    print(f'[进度] {data}')

@sio.on('disconnect')
def on_disconnect():
    print('[Socket.IO] 已断开')

try:
    print('连接 Socket.IO...')
    sio.connect('http://localhost:5000', transports=['polling'])
    print(f'连接状态: {sio.connected}')
    
    print('\n发送更新请求...')
    r = requests.post('http://localhost:5000/api/db/update')
    print(f'响应: {r.json()}')
    
    print('\n等待进度事件 (10秒)...')
    time.sleep(10)
    
    print('\n断开连接...')
    sio.disconnect()
    
except Exception as e:
    print(f'错误: {e}')
