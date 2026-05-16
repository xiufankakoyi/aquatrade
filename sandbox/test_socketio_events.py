#!/usr/bin/env python3
"""
测试 Socket.IO 事件是否能正确发送和接收
"""
import socketio
import time
import sys

# 创建 Socket.IO 客户端
sio = socketio.Client()

event_log = []

@sio.event
def connect():
    print("[✓] 已连接到服务器")
    print(f"    SID: {sio.sid}")

@sio.event
def disconnect():
    print("[✗] 断开连接")

@sio.event
def connect_error(data):
    print(f"[✗] 连接错误: {data}")

# 监听所有回测事件
event_types = [
    'initializing', 'initialized', 'backtest_start',
    'daily_equity', 'new_trade', 'metrics_update', 'final_metrics',
    'risk_data', 'risk_update', 'stream_complete', 'error', 'cancelled'
]

def make_event_handler(event_type):
    def handler(data):
        timestamp = time.strftime('%H:%M:%S')
        event_log.append((timestamp, event_type, data))
        print(f"[{timestamp}] 事件: {event_type}")
        if isinstance(data, dict):
            print(f"         数据: {str(data)[:200]}...")
        else:
            print(f"         数据: {data}")
    return handler

for event_type in event_types:
    sio.on(event_type, make_event_handler(event_type))

def run_test():
    try:
        print("=" * 60)
        print("Socket.IO 回测事件测试")
        print("=" * 60)
        
        # 连接到服务器
        print("\n[1] 连接服务器...")
        sio.connect('http://localhost:5000', transports=['polling', 'websocket'])
        time.sleep(1)
        
        if not sio.connected:
            print("[✗] 连接失败")
            return
        
        print("\n[2] 发送回测请求...")
        sio.emit('run_streaming_backtest', {
            'strategy_name': '聚宽量比市值策略pro',
            'start_date': '2024-05-20',
            'end_date': '2024-05-25',
            'benchmark_code': '000300'
        })
        print("[✓] 回测请求已发送")
        
        # 等待事件
        print("\n[3] 等待事件 (最多30秒)...")
        start_time = time.time()
        timeout = 30
        
        while time.time() - start_time < timeout:
            time.sleep(0.5)
            # 检查是否收到 stream_complete 或 error 事件
            for _, event_type, _ in event_log:
                if event_type in ['stream_complete', 'error']:
                    print(f"\n[✓] 收到结束事件: {event_type}")
                    break
            else:
                continue
            break
        
        elapsed = time.time() - start_time
        print(f"\n[4] 测试完成，耗时: {elapsed:.1f}秒")
        print(f"    共收到 {len(event_log)} 个事件")
        
        # 统计事件类型
        event_counts = {}
        for _, event_type, _ in event_log:
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        print("\n[5] 事件统计:")
        for event_type, count in sorted(event_counts.items()):
            print(f"    - {event_type}: {count}")
        
        # 检查关键事件
        print("\n[6] 关键事件检查:")
        has_backtest_start = any(e[1] == 'backtest_start' for e in event_log)
        has_daily_equity = any(e[1] == 'daily_equity' for e in event_log)
        has_new_trade = any(e[1] == 'new_trade' for e in event_log)
        has_stream_complete = any(e[1] == 'stream_complete' for e in event_log)
        has_error = any(e[1] == 'error' for e in event_log)
        
        print(f"    - backtest_start: {'✓' if has_backtest_start else '✗'}")
        print(f"    - daily_equity: {'✓' if has_daily_equity else '✗'}")
        print(f"    - new_trade: {'✓' if has_new_trade else '✗'}")
        print(f"    - stream_complete: {'✓' if has_stream_complete else '✗'}")
        print(f"    - error: {'✓' if has_error else '✗'}")
        
        if has_error:
            print("\n[⚠] 收到错误事件，详情:")
            for _, event_type, data in event_log:
                if event_type == 'error':
                    print(f"    {data}")
        
        sio.disconnect()
        
    except Exception as e:
        print(f"\n[✗] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    run_test()
