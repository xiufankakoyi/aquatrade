#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Server with SSE streaming support for real-time log display"""

import os
import sys
import subprocess
import threading
import json
import time
import queue
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
PORT = 9000
JOBS_FILE = os.path.join(BASE_DIR, 'jobs_state.json')

# 任务存储
jobs = {}
job_counter = 0
job_lock = threading.Lock()

# SSE 队列存储：job_id -> Queue
job_queues = {}

def load_jobs_from_file():
    global jobs, job_counter
    try:
        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    jobs = json.loads(content)
                    job_counter = max(int(k) for k in jobs.keys()) if jobs else 0
                else:
                    jobs = {}
                    job_counter = 0
        else:
            jobs = {}
            job_counter = 0
    except Exception as e:
        print(f"[WARNING] Failed to load jobs file: {e}")
        jobs = {}
        job_counter = 0

def save_jobs_to_file():
    try:
        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_or_create_queue(job_id):
    """获取或创建任务的 SSE 队列"""
    if job_id not in job_queues:
        job_queues[job_id] = queue.Queue()
    return job_queues[job_id]

def run_clean_and_push_background(job_id, date_arg):
    """运行数据清洗并推送到飞书（支持 SSE）"""
    cmd = f'python combined.py --date {date_arg}'
    print(f"[JOB {job_id}] Starting clean & push: {cmd}")
    
    q = get_or_create_queue(job_id)
    
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env
        )
        
        output_lines = []
        
        def read_output():
            """读取子进程输出并推送到队列"""
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    if line:
                        line_stripped = line.strip()
                        output_lines.append(line_stripped)
                        # 推送到 SSE 队列
                        q.put({
                            'type': 'log',
                            'message': line_stripped,
                            'timestamp': datetime.now().isoformat()
                        })
            finally:
                process.stdout.close()
        
        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()
        
        start_time = datetime.now()
        
        # 更新任务状态循环
        while process.poll() is None:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            with job_lock:
                jobs[job_id] = {
                    'status': 'running',
                    'date': date_arg,
                    'started_at': start_time.isoformat(),
                    'output': '\n'.join(output_lines[-30:]),
                    'progress_percent': min(int(elapsed / 10), 95),
                    'elapsed_seconds': int(elapsed),
                    'type': 'clean_push'
                }
                save_jobs_to_file()
            
            # 发送心跳保持连接
            q.put({'type': 'heartbeat', 'elapsed': int(elapsed)})
            time.sleep(0.5)
        
        reader_thread.join(timeout=2)
        return_code = process.wait()
        success = return_code == 0
        
        display_output = '\n'.join(output_lines)[-2000:]
        
        with job_lock:
            jobs[job_id] = {
                'status': 'completed',
                'success': success,
                'output': display_output,
                'progress_percent': 100,
                'elapsed_seconds': int((datetime.now() - start_time).total_seconds()),
                'completed_at': datetime.now().isoformat(),
                'type': 'clean_push'
            }
            save_jobs_to_file()
        
        # 发送完成消息到队列
        q.put({
            'type': 'completed',
            'success': success,
            'message': '任务完成' if success else '任务失败'
        })
        
        print(f"[JOB {job_id}] Clean & push completed: {success}")
        
    except Exception as e:
        print(f"[JOB {job_id}] Clean & push error: {e}")
        with job_lock:
            jobs[job_id] = {
                'status': 'completed',
                'success': False,
                'output': str(e),
                'progress_percent': 0,
                'type': 'clean_push'
            }
            save_jobs_to_file()
        q.put({
            'type': 'error',
            'message': str(e)
        })

def run_crawler_background(job_id, date_arg):
    """运行爬虫（支持 SSE）"""
    cmd = f'python run_crawler.py {date_arg}'
    print(f"[JOB {job_id}] Starting: {cmd}")
    
    api_list = [
        "ladder_trend_summary", "ladder_hierarchy_detail",
        "limit_up_filter", "sector_heat_stats",
        "market_sentiment_cycle", "dragon_tiger_list", "risk_monitor_list"
    ]
    
    q = get_or_create_queue(job_id)
    
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env
        )
        
        output_lines = []
        current_api = ""
        progress_percent = 0
        
        def read_output():
            """读取子进程输出并推送到队列"""
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    if line:
                        line_stripped = line.strip()
                        output_lines.append(line_stripped)
                        # 推送到 SSE 队列
                        q.put({
                            'type': 'log',
                            'message': line_stripped,
                            'timestamp': datetime.now().isoformat()
                        })
            finally:
                process.stdout.close()
        
        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()
        
        start_time = datetime.now()
        last_output_len = 0
        
        while process.poll() is None:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # 检测当前 API 进度
            if len(output_lines) > last_output_len:
                last_output_len = len(output_lines)
                if output_lines:
                    last_line = output_lines[-1]
                    for i, api in enumerate(api_list):
                        if api in last_line:
                            current_api = api
                            progress_percent = int((i + 1) / len(api_list) * 100)
                            # 发送进度更新
                            q.put({
                                'type': 'progress',
                                'api': current_api,
                                'percent': progress_percent
                            })
                            break
            
            with job_lock:
                jobs[job_id] = {
                    'status': 'running',
                    'date': date_arg,
                    'started_at': start_time.isoformat(),
                    'output': '\n'.join(output_lines[-30:]),
                    'current_api': current_api,
                    'progress_percent': progress_percent,
                    'elapsed_seconds': int(elapsed)
                }
                save_jobs_to_file()
            
            # 发送心跳
            q.put({'type': 'heartbeat', 'elapsed': int(elapsed)})
            time.sleep(0.5)
        
        reader_thread.join(timeout=2)
        return_code = process.wait()
        success = return_code == 0
        
        display_output = '\n'.join(output_lines)[-2000:]
        
        with job_lock:
            jobs[job_id] = {
                'status': 'completed',
                'success': success,
                'output': display_output,
                'current_api': '',
                'progress_percent': 100,
                'elapsed_seconds': int((datetime.now() - start_time).total_seconds()),
                'completed_at': datetime.now().isoformat()
            }
            save_jobs_to_file()
        
        # 发送完成消息
        q.put({
            'type': 'completed',
            'success': success,
            'message': '爬取完成' if success else '爬取失败'
        })
        
        print(f"[JOB {job_id}] Completed: {success}")
        
    except Exception as e:
        print(f"[JOB {job_id}] Error: {e}")
        with job_lock:
            jobs[job_id] = {
                'status': 'completed',
                'success': False,
                'output': str(e),
                'progress_percent': 0
            }
            save_jobs_to_file()
        q.put({
            'type': 'error',
            'message': str(e)
        })

class QuantRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        if self.path.startswith('/api/run'):
            self.handle_run_command()
        elif self.path.startswith('/api/clean-and-push'):
            self.handle_clean_and_push_command()
        elif self.path.startswith('/api/status'):
            self.handle_status_command()
        elif self.path.startswith('/api/error-report'):
            self.handle_error_report()
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path.startswith('/api/stream'):
            self.handle_sse_stream()
        elif self.path.startswith('/api/status'):
            self.handle_status_command()
        elif self.path.startswith('/api/report'):
            self.handle_get_report()
        else:
            super().do_GET()
    
    def handle_sse_stream(self):
        """SSE 流式推送端点"""
        try:
            parsed = urlparse(self.path)
            params = dict(parse_qs(parsed.query))
            job_id = int(params.get('job_id', [0])[0])
            
            # 检查任务是否存在
            with job_lock:
                if job_id not in jobs:
                    self.send_json_response({'success': False, 'error': 'Job not found'})
                    return
            
            # 获取队列
            q = get_or_create_queue(job_id)
            
            # 发送 SSE 响应头
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            print(f"[SSE] Client connected to job {job_id}")
            
            # 流式推送
            while True:
                try:
                    # 从队列获取消息（超时1秒）
                    msg = q.get(timeout=1)
                    
                    # 发送 SSE 格式数据
                    data = json.dumps(msg, ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode('utf-8'))
                    self.wfile.flush()
                    
                    # 如果是完成或错误消息，结束流
                    if msg['type'] in ('completed', 'error'):
                        break
                        
                except queue.Empty:
                    # 发送注释保持连接
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    
                    # 检查任务是否已完成
                    with job_lock:
                        if jobs.get(job_id, {}).get('status') == 'completed':
                            break
            
            print(f"[SSE] Client disconnected from job {job_id}")
            
        except Exception as e:
            print(f"[SSE] Error: {e}")
    
    def handle_run_command(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))

            date_arg = params.get('date', '')
            if not date_arg:
                self.send_json_response({'success': False, 'error': 'Missing date'})
                return

            global job_counter
            with job_lock:
                job_counter += 1
                job_id = job_counter

            jobs[job_id] = {
                'status': 'running',
                'date': date_arg,
                'started_at': datetime.now().isoformat(),
                'output': 'Starting crawler...',
                'progress_percent': 0
            }
            save_jobs_to_file()

            thread = threading.Thread(
                target=run_crawler_background,
                args=(job_id, date_arg),
                daemon=True
            )
            thread.start()

            print(f"[INFO] Job {job_id} started: {date_arg}")
            self.send_json_response({
                'success': True,
                'job_id': job_id,
                'message': 'Crawler started'
            })

        except Exception as e:
            import traceback
            print(f"[ERROR] {e}")
            traceback.print_exc()
            self.send_json_response({'success': False, 'error': str(e)})

    def handle_clean_and_push_command(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            params = json.loads(post_data.decode('utf-8'))

            date_arg = params.get('date', '')
            if not date_arg:
                self.send_json_response({'success': False, 'error': 'Missing date'})
                return

            global job_counter
            with job_lock:
                job_counter += 1
                job_id = job_counter

            jobs[job_id] = {
                'status': 'running',
                'date': date_arg,
                'started_at': datetime.now().isoformat(),
                'output': 'Starting clean and push...',
                'progress_percent': 0,
                'type': 'clean_push'
            }
            save_jobs_to_file()

            thread = threading.Thread(
                target=run_clean_and_push_background,
                args=(job_id, date_arg),
                daemon=True
            )
            thread.start()

            print(f"[INFO] Clean & Push Job {job_id} started: {date_arg}")
            self.send_json_response({
                'success': True,
                'job_id': job_id,
                'message': 'Clean and push started'
            })

        except Exception as e:
            import traceback
            print(f"[ERROR] {e}")
            traceback.print_exc()
            self.send_json_response({'success': False, 'error': str(e)})
    
    def handle_status_command(self):
        """原有的轮询接口（作为 fallback）"""
        try:
            parsed = urlparse(self.path)
            params = dict(parse_qs(parsed.query))
            job_id = int(params.get('job_id', [0])[0])
            
            with job_lock:
                if job_id in jobs:
                    job = jobs[job_id]
                    self.send_json_response({'success': True, 'job': job})
                else:
                    self.send_json_response({'success': False, 'error': 'Job not found'})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def handle_error_report(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            print(f"[ERROR-REPORT] {post_data.decode('utf-8')[:200]}")
            self.send_json_response({'success': True})
        except:
            self.send_json_response({'success': False})
    
    def handle_get_report(self):
        """获取生成的报告文件内容"""
        try:
            parsed = urlparse(self.path)
            params = dict(parse_qs(parsed.query))
            date = params.get('date', [''])[0]
            
            if not date:
                self.send_json_response({'success': False, 'error': 'Missing date parameter'})
                return
            
            # 构建报告文件路径
            report_path = os.path.join(BASE_DIR, 'data', 'cleaned_data', date, 'ai_daily_brief.txt')
            
            if not os.path.exists(report_path):
                self.send_json_response({'success': False, 'error': 'Report not found'})
                return
            
            # 读取报告内容
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.send_json_response({
                'success': True,
                'content': content,
                'date': date
            })
            
        except Exception as e:
            print(f"[ERROR] Failed to read report: {e}")
            self.send_json_response({'success': False, 'error': str(e)})
    
    def send_json_response(self, data):
        response = json.dumps(data, ensure_ascii=False)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

if __name__ == '__main__':
    load_jobs_from_file()
    os.chdir(BASE_DIR)
    try:
        server = HTTPServer(('0.0.0.0', PORT), QuantRequestHandler)
        print("=" * 60)
        print(f"  Quant Crawler Web Service Started")
        print(f"  Access URL: http://localhost:{PORT}")
        print(f"  SSE Endpoint: /api/stream?job_id=<id>")
        print("=" * 60)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped")
