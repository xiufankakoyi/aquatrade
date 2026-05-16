#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查后端启动错误
"""
import subprocess
import sys
import time

def check_backend_errors():
    """启动后端并捕获错误日志"""
    print("启动后端服务并捕获错误...")
    
    process = subprocess.Popen(
        ['honcho', 'start'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    errors = []
    warnings = []
    start_time = time.time()
    
    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
                
            # 检查错误
            if any(keyword in line.lower() for keyword in ['error', 'unable', 'failed', 'cannot', 'exception']):
                errors.append(line)
                print(f"[ERROR] {line}")
            
            # 检查警告
            elif any(keyword in line.lower() for keyword in ['warning']):
                warnings.append(line)
                print(f"[WARNING] {line}")
            
            # 运行 30 秒或收集到足够错误后退出
            if time.time() - start_time > 30 or len(errors) >= 20:
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()
    
    print("\n" + "="*80)
    print(f"捕获到 {len(errors)} 个错误, {len(warnings)} 个警告")
    print("="*80)
    
    if errors:
        print("\n错误列表:")
        for i, err in enumerate(errors[:10], 1):
            print(f"{i}. {err}")
    
    return errors, warnings

if __name__ == '__main__':
    check_backend_errors()
