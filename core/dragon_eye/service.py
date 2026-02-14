"""
DragonEye 模块核心服务：编排爬虫、清洗、入库与推送
支持 SSE 实时日志推送和任务状态管理
"""
import subprocess
import sys
import json
import threading
import queue
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from config.config import Config
from config.logger import get_logger
from core.dragon_eye.manager import DragonEyeManager
from core.dragon_eye.job_manager import job_manager, JobStatus
from data_svc.spiders.dragon_spider.cleaner import StockDataCleaner

logger = get_logger(__name__)


class LogCapture:
    """
    日志捕获器，用于实时捕获子进程输出
    支持 SSE 流式推送
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.log_queue = queue.Queue()
        self.subscribers: list[Callable] = []
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
    
    def start_capture(self, process: subprocess.Popen):
        """开始捕获进程输出"""
        self._capture_thread = threading.Thread(
            target=self._capture_output,
            args=(process,),
            daemon=True
        )
        self._capture_thread.start()
    
    def _capture_output(self, process: subprocess.Popen):
        """在后台线程中捕获输出"""
        try:
            # 捕获 stdout
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if self._stop_event.is_set():
                        break
                    if line:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'level': 'info',
                            'message': line.strip()
                        }
                        self.log_queue.put(log_entry)
                        self._notify_subscribers(log_entry)
            
            # 捕获 stderr
            if process.stderr:
                for line in iter(process.stderr.readline, ''):
                    if self._stop_event.is_set():
                        break
                    if line:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'level': 'error',
                            'message': line.strip()
                        }
                        self.log_queue.put(log_entry)
                        self._notify_subscribers(log_entry)
                        
        except Exception as e:
            logger.error(f"Log capture error: {e}")
    
    def subscribe(self, callback: Callable[[Dict], None]):
        """订阅日志更新"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        self.subscribers = [cb for cb in self.subscribers if cb != callback]
    
    def _notify_subscribers(self, log_entry: Dict):
        """通知所有订阅者"""
        for callback in self.subscribers:
            try:
                callback(log_entry)
            except Exception as e:
                logger.error(f"Error notifying log subscriber: {e}")
    
    def stop(self):
        """停止捕获"""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=2)


class DragonEyeService:
    """
    DragonEye 核心服务类
    
    功能：
    1. 启动爬虫并实时捕获日志
    2. 执行数据清洗和持久化
    3. 推送飞书消息
    4. 管理任务状态和 SSE 流
    """
    
    def __init__(self):
        self.manager = DragonEyeManager()
        self.project_root = Path(Config.BASE_DIR)
        self.spider_path = self.project_root / "data_svc" / "spiders" / "dragon_spider" / "main.py"
        self.cleaner_path = self.project_root / "data_svc" / "spiders" / "dragon_spider" / "cleaner.py"
        self.data_lake_dir = self.project_root / "data" / "spider_data" / "dragon_eye" / "data_lake"
        self._active_captures: Dict[str, LogCapture] = {}
    
    def run_crawler(self, target_date: str, job_id: Optional[str] = None) -> str:
        """
        启动爬虫任务
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            job_id: 可选的任务ID
            
        Returns:
            job_id: 任务ID
        """
        # 创建任务
        job = job_manager.create_job('crawl', job_id)
        job_id = job.job_id
        
        # 在后台线程中执行爬虫
        thread = threading.Thread(
            target=self._run_crawler_task,
            args=(target_date, job_id),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def _run_crawler_task(self, target_date: str, job_id: str):
        """在后台执行爬虫任务"""
        job_manager.update_job(job_id, status='running')
        job_manager.add_log(job_id, 'info', f'🚀 启动爬虫任务，目标日期: {target_date}', 0)
        
        try:
            cmd = [sys.executable, str(self.spider_path), '--date', target_date]
            
            job_manager.add_log(job_id, 'info', f'执行命令: {" ".join(cmd)}', 5)
            
            # 启动子进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            # 创建日志捕获器
            capture = LogCapture(job_id)
            self._active_captures[job_id] = capture
            
            # 同步日志到 job_manager
            def on_log(log_entry):
                job_manager.add_log(
                    job_id, 
                    log_entry['level'], 
                    log_entry['message']
                )
            
            capture.subscribe(on_log)
            capture.start_capture(process)
            
            # 等待进程完成
            return_code = process.wait()
            capture.stop()
            
            if return_code == 0:
                job_manager.add_log(job_id, 'success', '✅ 爬虫任务完成', 100)
                job_manager.complete_job(job_id, success=True)
            else:
                error_msg = f'爬虫进程异常退出，返回码: {return_code}'
                job_manager.add_log(job_id, 'error', f'❌ {error_msg}')
                job_manager.complete_job(job_id, success=False, error=error_msg)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Crawler task failed: {e}")
            job_manager.add_log(job_id, 'error', f'❌ 任务执行异常: {error_msg}')
            job_manager.complete_job(job_id, success=False, error=error_msg)
        finally:
            if job_id in self._active_captures:
                del self._active_captures[job_id]
    
    def process_and_persist(self, target_date: str, job_id: Optional[str] = None) -> str:
        """
        清洗数据并持久化到 LanceDB
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            job_id: 可选的任务ID
            
        Returns:
            job_id: 任务ID
        """
        job = job_manager.create_job('clean', job_id)
        job_id = job.job_id
        
        thread = threading.Thread(
            target=self._process_task,
            args=(target_date, job_id),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def _process_task(self, target_date: str, job_id: str):
        """在后台执行清洗任务"""
        job_manager.update_job(job_id, status='running')
        job_manager.add_log(job_id, 'info', f'🧹 开始数据清洗，日期: {target_date}', 0)
        
        try:
            date_dir = self.data_lake_dir / target_date
            if not date_dir.exists():
                error_msg = f'数据目录不存在: {date_dir}'
                job_manager.add_log(job_id, 'error', f'❌ {error_msg}')
                job_manager.complete_job(job_id, success=False, error=error_msg)
                return
            
            job_manager.add_log(job_id, 'info', '加载数据文件...', 10)
            cleaner = StockDataCleaner(str(date_dir))
            
            # 1. 生成大盘情绪数据
            job_manager.add_log(job_id, 'info', '生成市场仪表盘...', 30)
            sentiment_summary = cleaner.generate_market_dashboard()
            if sentiment_summary:
                import pandas as pd
                df_sent = pd.DataFrame([sentiment_summary])
                self.manager.upsert_sentiment(df_sent)
                job_manager.add_log(
                    job_id, 'success', 
                    f'✅ 大盘情绪数据已入库: 炸板率 {sentiment_summary.get("broken_ratio", 0):.2%}', 
                    50
                )
            
            # 2. 生成龙头个股数据
            job_manager.add_log(job_id, 'info', '生成个股特征矩阵...', 60)
            stock_matrix = cleaner.generate_stock_feature_matrix()
            if stock_matrix:
                import pandas as pd
                df_stocks = pd.DataFrame(stock_matrix)
                self.manager.upsert_stocks(df_stocks)
                job_manager.add_log(
                    job_id, 'success', 
                    f'✅ 龙头个股数据已入库: {len(stock_matrix)} 只股票', 
                    80
                )
            
            # 3. 生成 AI 简报
            job_manager.add_log(job_id, 'info', '生成 AI 每日复盘简报...', 90)
            cleaner.generate_ai_daily_brief()
            job_manager.add_log(job_id, 'success', '✅ AI 简报生成完成', 95)
            
            job_manager.add_log(job_id, 'success', '🎉 数据清洗和入库完成', 100)
            job_manager.complete_job(job_id, success=True)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Process task failed: {e}")
            job_manager.add_log(job_id, 'error', f'❌ 清洗失败: {error_msg}')
            job_manager.complete_job(job_id, success=False, error=error_msg)
    
    def run_full_pipeline(self, target_date: str, push_feishu: bool = True) -> str:
        """
        执行完整工作流：爬虫 -> 清洗 -> (推送)
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            push_feishu: 是否推送到飞书
            
        Returns:
            job_id: 任务ID
        """
        job = job_manager.create_job('full_pipeline')
        job_id = job.job_id
        
        thread = threading.Thread(
            target=self._run_pipeline_task,
            args=(target_date, job_id, push_feishu),
            daemon=True
        )
        thread.start()
        
        return job_id
    
    def _run_pipeline_task(self, target_date: str, job_id: str, push_feishu: bool):
        """在后台执行完整工作流"""
        job_manager.update_job(job_id, status='running')
        
        try:
            # Step 1: 爬虫
            job_manager.add_log(job_id, 'info', '📡 步骤 1/3: 启动数据爬虫...', 5)
            
            cmd = [sys.executable, str(self.spider_path), '--date', target_date]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            capture = LogCapture(job_id)
            self._active_captures[job_id] = capture
            
            def on_log(log_entry):
                job_manager.add_log(job_id, log_entry['level'], log_entry['message'])
            
            capture.subscribe(on_log)
            capture.start_capture(process)
            
            return_code = process.wait()
            capture.stop()
            
            if return_code != 0:
                raise Exception(f'爬虫进程异常退出，返回码: {return_code}')
            
            job_manager.add_log(job_id, 'success', '✅ 爬虫完成', 35)
            
            # Step 2: 清洗
            job_manager.add_log(job_id, 'info', '🧹 步骤 2/3: 开始数据清洗...', 40)
            
            date_dir = self.data_lake_dir / target_date
            cleaner = StockDataCleaner(str(date_dir))
            
            sentiment_summary = cleaner.generate_market_dashboard()
            if sentiment_summary:
                import pandas as pd
                df_sent = pd.DataFrame([sentiment_summary])
                self.manager.upsert_sentiment(df_sent)
            
            stock_matrix = cleaner.generate_stock_feature_matrix()
            if stock_matrix:
                import pandas as pd
                df_stocks = pd.DataFrame(stock_matrix)
                self.manager.upsert_stocks(df_stocks)
            
            cleaner.generate_ai_daily_brief()
            job_manager.add_log(job_id, 'success', '✅ 数据清洗完成', 70)
            
            # Step 3: 推送 (可选)
            if push_feishu:
                job_manager.add_log(job_id, 'info', '📤 步骤 3/3: 推送到飞书...', 75)
                success, msg = self.send_to_feishu(target_date)
                if success:
                    job_manager.add_log(job_id, 'success', f'✅ 飞书推送成功', 100)
                else:
                    job_manager.add_log(job_id, 'warning', f'⚠️ 飞书推送失败: {msg}', 100)
            else:
                job_manager.add_log(job_id, 'info', '⏭️ 跳过飞书推送', 100)
            
            job_manager.complete_job(job_id, success=True)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Pipeline task failed: {e}")
            job_manager.add_log(job_id, 'error', f'❌ 工作流失败: {error_msg}')
            job_manager.complete_job(job_id, success=False, error=error_msg)
        finally:
            if job_id in self._active_captures:
                del self._active_captures[job_id]
    
    def get_latest_brief(self, target_date: str) -> str:
        """获取最新的 AI 简报内容"""
        brief_path = self.data_lake_dir / target_date / "ai_daily_brief.txt"
        if brief_path.exists():
            return brief_path.read_text(encoding='utf-8')
        return ""
    
    def send_to_feishu(self, target_date: str) -> tuple[bool, str]:
        """
        触发飞书推送
        
        Returns:
            (success, message)
        """
        from core.dragon_eye.combined import FeishuPush
        
        webhook_url = getattr(Config, 'FEISHU_WEBHOOK', "")
        if not webhook_url:
            return False, "Feishu Webhook not configured"
        
        brief_content = self.get_latest_brief(target_date)
        if not brief_content:
            return False, "Brief content is empty"
        
        try:
            pusher = FeishuPush(webhook_url)
            markdown = pusher.txt_to_markdown(brief_content)
            success = pusher.push_markdown(markdown)
            return success, "Pushed to Feishu" if success else "Failed to push"
        except Exception as e:
            return False, str(e)
    
    def subscribe_job_logs(self, job_id: str, callback: Callable[[Dict], None]):
        """订阅任务日志流"""
        if job_id in self._active_captures:
            self._active_captures[job_id].subscribe(callback)
            return True
        
        # 如果任务已完成，直接发送历史日志
        job = job_manager.get_job(job_id)
        if job:
            for log in job.logs:
                callback(log)
        return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """获取任务状态"""
        job = job_manager.get_job(job_id)
        return job.to_dict() if job else None
