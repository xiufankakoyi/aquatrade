#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
捕获后端启动日志
"""
import subprocess
import sys
import time
import threading
import queue

def read_output(pipe, output_queue):
    """读取输出到队列"""
    try:
        for line in iter(pipe.readline, ''):
            output_queue.put(line.strip())
    except:
        pass
    finally:
        pipe.close()

def capture_backend_logs():
    """捕获后端日志"""
    print("="*80)
    print("启动后端服务并捕获日志...")
    print("="*80)
    
    # 启动进程
    process = subprocess.Popen(
        ['honcho', 'start'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='ignore',
        bufsize=1
    )
    
    # 创建队列和线程
    output_queue = queue.Queue()
    reader_thread = threading.Thread(target=read_output, args=(process.stdout, output_queue))
    reader_thread.daemon = True
    reader_thread.start()
    
    errors = []
    warnings = []
    all_logs = []
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < 30:  # 运行30秒
            try:
                line = output_queue.get(timeout=1)
                all_logs.append(line)
                
                # 检查错误
                if any(k in line.lower() for k in ['error', 'unable', 'failed', 'cannot', 'exception']) and 'unicodeencodeerror' not in line.lower():
                    errors.append(line)
                    print(f"[ERROR] {line}")
                # 检查警告
                elif any(k in line.lower() for k in ['warning']) and 'lifespan' not in line.lower():
                    warnings.append(line)
                    print(f"[WARNING] {line}")
                # 打印关键信息
                elif any(k in line for k in ['PositionManager', 'WatchlistManager', 'ts_code', 'parquet', 'industry']):
                    print(f"[INFO] {line}")
                    
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
                
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()
    
    # 保存完整日志
    with open('sandbox/backend_full_logs.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_logs))
    
    print("\n" + "="*80)
    print(f"捕获到 {len(errors)} 个错误, {len(warnings)} 个警告")
    print(f"完整日志已保存到: sandbox/backend_full_logs.txt")
    print("="*80)
    
    if errors:
        print("\n错误列表:")
        for i, err in enumerate(errors[:15], 1):
            print(f"{i}. {err}")
    
    return errors, warnings

if __name__ == '__main__':
    capture_backend_logs()
