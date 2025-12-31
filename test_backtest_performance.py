"""
使用 Python SocketIO 客户端测试回测性能
直接发送请求并监控性能指标
"""
import json
import time
from pathlib import Path
import socketio
import requests
import sys

# 配置
BACKEND_URL = "http://localhost:5000"
LOG_FILE = Path(r"d:\aquatrade\.cursor\debug.log")

def check_backend_available(max_retries=10, retry_interval=2):
    """检查后端是否可用"""
    print(f"[CHECK] 检查后端是否运行: {BACKEND_URL}")
    for i in range(max_retries):
        try:
            response = requests.get(BACKEND_URL, timeout=2)
            if response.status_code == 200:
                print(f"[CHECK] 后端已就绪 (尝试 {i+1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            if i < max_retries - 1:
                print(f"[CHECK] 后端未就绪，等待 {retry_interval} 秒后重试... ({i+1}/{max_retries})")
                time.sleep(retry_interval)
            else:
                print(f"[CHECK] 后端未就绪，请先启动后端服务")
                return False
    return False

def analyze_logs():
    """分析日志文件"""
    if not LOG_FILE.exists():
        print(f"[LOG] 日志文件不存在: {LOG_FILE}")
        return
    
    print(f"\n[LOG] 分析日志文件: {LOG_FILE}")
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"  日志行数: {len(lines)}")
        
        # 统计关键指标
        query_times = []
        batch_times = []
        signal_times = []
        errors = []
        
        for line_num, line in enumerate(lines, 1):
            try:
                log_entry = json.loads(line.strip())
                location = log_entry.get('location', '')
                message = log_entry.get('message', '')
                data = log_entry.get('data', {})
                
                # 统计查询时间
                if 'get_trading_dates' in location and 'query_time' in data:
                    query_times.append({
                        'time': data['query_time'],
                        'line': line_num,
                        'rows': data.get('rows', 0)
                    })
                
                # 统计批次加载时间
                if 'load_batch' in location and 'elapsed' in data:
                    batch_times.append({
                        'time': data['elapsed'],
                        'line': line_num,
                        'rows': data.get('rows', 0)
                    })
                
                # 统计信号生成时间
                if 'generate_signals' in location and 'elapsed' in data:
                    signal_times.append({
                        'time': data['elapsed'],
                        'line': line_num,
                        'date': data.get('date', '')
                    })
                
                # 收集错误
                if 'error' in message.lower() or '失败' in message:
                    errors.append({
                        'line': line_num,
                        'location': location,
                        'message': message,
                        'error': data.get('error', '')
                    })
            except Exception as e:
                print(f"  [WARN] 解析日志行 {line_num} 失败: {e}")
        
        # 输出统计结果
        if query_times:
            times = [q['time'] for q in query_times]
            print(f"\n  查询时间统计 (get_trading_dates):")
            print(f"    次数: {len(query_times)}")
            print(f"    平均: {sum(times)/len(times):.3f}s")
            print(f"    最大: {max(times):.3f}s (行 {max(query_times, key=lambda x: x['time'])['line']})")
            print(f"    最小: {min(times):.3f}s")
            if max(times) > 1.0:
                print(f"    ⚠️  警告: 有查询超过 1 秒！")
        
        if batch_times:
            times = [b['time'] for b in batch_times]
            print(f"\n  批次加载时间统计 (load_batch):")
            print(f"    次数: {len(batch_times)}")
            print(f"    平均: {sum(times)/len(times):.3f}s")
            print(f"    最大: {max(times):.3f}s")
            print(f"    最小: {min(times):.3f}s")
            if max(times) > 10.0:
                print(f"    ⚠️  警告: 有批次加载超过 10 秒！")
        
        if signal_times:
            times = [s['time'] for s in signal_times]
            print(f"\n  信号生成时间统计 (generate_signals):")
            print(f"    次数: {len(signal_times)}")
            print(f"    平均: {sum(times)/len(times):.3f}s")
            print(f"    最大: {max(times):.3f}s")
            print(f"    最小: {min(times):.3f}s")
        
        if errors:
            print(f"\n  错误统计:")
            print(f"    错误数量: {len(errors)}")
            for error in errors[:5]:  # 只显示前5个错误
                print(f"    行 {error['line']}: {error['message']}")
                if error['error']:
                    print(f"      详情: {error['error'][:100]}")

def test_backtest():
    """测试回测性能"""
    print("=" * 60)
    print("回测性能测试")
    print("=" * 60)
    
    # 清除之前的日志
    if LOG_FILE.exists():
        LOG_FILE.unlink()
        print(f"[TEST] 已清除日志文件: {LOG_FILE}")
    
    # 创建 SocketIO 客户端
    sio = socketio.Client()
    
    updates = []
    start_time = None
    result = None
    error = None
    
    @sio.event
    def connect():
        print("[SocketIO] 连接成功")
        nonlocal start_time
        start_time = time.time()
        
        # 发送回测请求
        backtest_data = {
            'strategy_name': '聚宽量比市值策略pro',
            'start_date': '2024-05-20',
            'end_date': '2024-05-21',
            'benchmark_code': '000300',
            'params': {}
        }
        
        print(f"[TEST] 发送回测请求: {backtest_data}")
        sio.emit('run_streaming_backtest', backtest_data)
    
    @sio.event
    def connect_error(data):
        print(f"[SocketIO] 连接失败: {data}")
        nonlocal error
        error = f"连接失败: {data}"
    
    @sio.event
    def disconnect():
        print("[SocketIO] 连接断开")
    
    @sio.on('backtest_update')
    def on_backtest_update(data):
        elapsed = time.time() - start_time if start_time else 0
        update_type = data.get('type', 'unknown')
        updates.append({
            'type': update_type,
            'elapsed': elapsed,
            'timestamp': time.time()
        })
        print(f"[回测更新] {update_type} ({elapsed:.2f}s)")
    
    @sio.on('backtest_complete')
    def on_backtest_complete(data):
        elapsed = time.time() - start_time if start_time else 0
        print(f"[回测完成] 总耗时: {elapsed:.2f}s")
        nonlocal result
        result = {
            'success': True,
            'totalTime': elapsed,
            'updates': updates,
            'result': data
        }
        sio.disconnect()
    
    @sio.on('backtest_error')
    def on_backtest_error(data):
        elapsed = time.time() - start_time if start_time else 0
        error_msg = data.get('error', '未知错误') if isinstance(data, dict) else str(data)
        print(f"[回测错误] {error_msg} ({elapsed:.2f}s)")
        nonlocal error
        error = error_msg
        result = {
            'success': False,
            'totalTime': elapsed,
            'error': error_msg
        }
        sio.disconnect()
    
    # 检查后端是否可用
    if not check_backend_available():
        print("\n[ERROR] 后端服务未运行，请先启动后端:")
        print("  1. 运行 start.bat")
        print("  2. 或者手动启动: granian --interface asgi --host 0.0.0.0 --port 5000 run:app_asgi")
        return None
    
    try:
        print(f"[TEST] 连接到后端: {BACKEND_URL}")
        sio.connect(BACKEND_URL, wait_timeout=10)
        
        # 等待回测完成（最多5分钟）
        print("[TEST] 等待回测完成...")
        sio.wait(timeout=300)
        
    except Exception as e:
        print(f"[TEST] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        error = str(e)
    finally:
        if sio.connected:
            sio.disconnect()
    
    # 分析日志
    analyze_logs()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    
    if result:
        print(f"成功: {result.get('success', False)}")
        print(f"总耗时: {result.get('totalTime', 0):.2f}秒")
        print(f"更新次数: {len(result.get('updates', []))}")
        if result.get('error'):
            print(f"错误: {result['error']}")
    elif error:
        print(f"错误: {error}")
    else:
        print("测试未完成（可能超时）")
    
    return result

if __name__ == "__main__":
    test_backtest()
