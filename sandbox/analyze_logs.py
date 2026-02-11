#!/usr/bin/env python3
"""分析性能日志"""
import json

log_file = r'd:\aquatrade\.cursor\debug.log'

# 读取最后 10000 行
with open(log_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    recent_lines = lines[-10000:]

# 查找性能日志
perf_logs = []
error_logs = []

for line in recent_lines:
    try:
        log = json.loads(line.strip())
        location = log.get('location', '')
        message = log.get('message', '')
        data = log.get('data', {})
        
        if 'get_stock_pool' in location or 'generate_signals' in location:
            perf_logs.append(log)
        
        if 'is_st' in str(log) or 'KeyError' in str(log) or '策略信号生成失败' in message:
            error_logs.append(log)
    except:
        pass

print(f"=== 性能日志 (最近 {len(perf_logs)} 条) ===")
for log in perf_logs[-10:]:
    location = log.get('location', '')
    message = log.get('message', '')
    elapsed = log.get('data', {}).get('elapsed', 'N/A')
    print(f"{location}: {message} - elapsed: {elapsed}")

print(f"\n=== 错误日志 (最近 {len(error_logs)} 条) ===")
for log in error_logs[:5]:
    location = log.get('location', '')
    message = log.get('message', '')
    error = log.get('data', {}).get('error', 'N/A')
    traceback = log.get('data', {}).get('traceback', 'N/A')[:200]
    print(f"{location}: {message}")
    print(f"  Error: {error}")
    if traceback != 'N/A':
        print(f"  Traceback: {traceback}")

