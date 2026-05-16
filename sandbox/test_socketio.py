import socketio
import time

sio = socketio.Client()

results = []

@sio.event
def connect():
    print('Connected!')
    sio.emit('start_backtest', {
        'strategy_name': 'simple_volume_v5',
        'start_date': '2024-01-01',
        'end_date': '2024-01-31',
        'params': {}
    })

@sio.event
def disconnect():
    print('Disconnected!')

@sio.event
def backtest_start(data):
    print(f'backtest_start: {data}')

@sio.event
def daily_update(data):
    results.append(data)
    if len(results) % 5 == 0:
        print(f'daily_update: {len(results)} received')

@sio.event
def new_trade(data):
    print(f'new_trade: {data}')

@sio.event
def stream_complete(data):
    print(f'stream_complete: {data}')
    print(f'Total daily updates: {len(results)}')
    sio.disconnect()

@sio.event
def error(data):
    print(f'error: {data}')

try:
    # 指定 socketio_path
    sio.connect('http://localhost:5000', transports=['polling'], socketio_path='socket.io')
    sio.wait()
    print('Test completed successfully!')
except Exception as e:
    print(f'Connection error: {e}')
