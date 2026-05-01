"""
启动服务 - 三阶段自检
负责环境检查、数据完整性校验、内核初始化
"""
import os
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from config.logger import get_logger
from config.config import Config


class StartupPhase(Enum):
    IDLE = "idle"
    ENVIRONMENT = "environment"
    INTEGRITY = "integrity"
    KERNEL = "kernel"
    READY = "ready"
    ERROR = "error"


class ErrorCode(Enum):
    ERR_REDIS_CONN = "ERR_REDIS_CONN"
    ERR_REDIS_PORT = "ERR_REDIS_PORT"
    ERR_DATA_MISSING = "ERR_DATA_MISSING"
    ERR_DATA_CORRUPT = "ERR_DATA_CORRUPT"
    ERR_KERNEL_INIT = "ERR_KERNEL_INIT"
    ERR_TIMEOUT = "ERR_TIMEOUT"
    ERR_DATA_UPDATE = "ERR_DATA_UPDATE"


@dataclass
class StartupStatus:
    phase: str = "idle"
    step: str = "initializing"
    message: str = "正在唤醒 AquaTrade..."
    progress: int = 0
    ready: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "step": self.step,
            "message": self.message,
            "progress": self.progress,
            "ready": self.ready,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "logs": self.logs[-20:],
        }


class StartupService:
    """
    三阶段自检服务
    
    Phase 1: Environment - 环境检查 (Redis端口、数据库权限)
    Phase 2: Integrity - 数据完整性 (Parquet文件校验)
    Phase 3: Kernel - 内核初始化 (策略引擎实例化)
    """
    
    _instance: Optional['StartupService'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.logger = get_logger(__name__)
        self.status = StartupStatus()
        self._startup_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._daily_update_timer: Optional[threading.Timer] = None
        
        self.required_lancedb_tables = [
            ("daily_ohlcv", True, "K线数据"),
            ("stock_info", True, "股票信息"),
            ("index_daily", False, "指数数据"),
            ("factors", False, "因子数据"),
        ]
        
        # 自动数据更新配置
        self.auto_update_enabled = os.getenv("AUTO_UPDATE_ON_STARTUP", "true").lower() == "true"
        self.max_update_wait_seconds = int(os.getenv("MAX_UPDATE_WAIT_SECONDS", "300"))  # 默认5分钟超时
        
        # 每日更新检查配置
        self.daily_update_enabled = os.getenv("DAILY_UPDATE_ENABLED", "true").lower() == "true"
        self.daily_update_hour = int(os.getenv("DAILY_UPDATE_HOUR", "9"))  # 默认早上9点
        self._last_update_date: Optional[str] = None  # 记录上次更新日期
    
    def add_log(self, level: str, message: str):
        """添加日志条目"""
        timestamp = time.strftime("%H:%M:%S")
        self.status.logs.append({
            "timestamp": timestamp,
            "level": level,
            "message": message
        })
        self.logger.info(f"[Startup] [{level}] {message}")
    
    def update_status(self, phase: str, step: str, message: str, progress: int):
        """更新状态"""
        self.status.phase = phase
        self.status.step = step
        self.status.message = message
        self.status.progress = progress
    
    def set_error(self, error_code: ErrorCode, message: str):
        """设置错误状态"""
        self.status.phase = StartupPhase.ERROR.value
        self.status.error_code = error_code.value
        self.status.error_message = message
        self.status.message = message
        self.add_log("ERROR", message)
    
    def check_environment(self) -> bool:
        """
        Phase 1: 环境检查
        - Redis 连接
        - 数据库权限
        """
        self.update_status("environment", "checking_redis", "正在检查 Redis 连接...", 10)
        
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(redis_url, socket_timeout=5)
            client.ping()
            self.add_log("INFO", f"Redis {redis_url} ... OK")
        except redis.ConnectionError as e:
            self.set_error(ErrorCode.ERR_REDIS_CONN, f"Redis 连接失败: {e}")
            return False
        except Exception as e:
            self.set_error(ErrorCode.ERR_REDIS_CONN, f"Redis 检查异常: {e}")
            return False
        
        self.update_status("environment", "checking_db", "正在检查数据库权限...", 20)
        
        db_path = Config.DB_PATH
        db_dir = Path(db_path).parent
        if db_dir.exists():
            if os.access(db_dir, os.W_OK):
                self.add_log("INFO", f"数据库目录 {db_dir} ... 可写")
            else:
                self.add_log("WARN", f"数据库目录 {db_dir} ... 只读")
        else:
            self.add_log("WARN", f"数据库目录 {db_dir} ... 不存在，将自动创建")
        
        return True
    
    def check_integrity(self) -> bool:
        """
        Phase 2: 数据完整性检查
        - LanceDB 表存在性
        - 数据行数校验
        """
        self.update_status("integrity", "checking_lancedb", "正在校验 LanceDB 数据库...", 30)
        
        try:
            import lancedb
            lancedb_path = getattr(Config, 'LANCEDB_PATH', None)
            if lancedb_path is None:
                lancedb_path = str(Path(__file__).parent.parent.parent / "data" / "lancedb")
            
            db = lancedb.connect(lancedb_path)
            result = db.list_tables()
            existing_tables = result.tables if hasattr(result, 'tables') else list(result)
        except Exception as e:
            self.set_error(ErrorCode.ERR_DATA_MISSING, f"LanceDB 连接失败: {e}")
            return False
        
        missing_required = []
        
        for i, (table_name, required, description) in enumerate(self.required_lancedb_tables):
            progress = 30 + int((i + 1) / len(self.required_lancedb_tables) * 30)
            self.update_status("integrity", f"checking_{table_name}", 
                             f"正在检查 {description}...", progress)
            
            if table_name in existing_tables:
                try:
                    table = db.open_table(table_name)
                    row_count = table.count_rows()
                    if row_count > 0:
                        self.add_log("INFO", f"{table_name} ... {row_count:,} rows")
                    else:
                        self.add_log("WARN", f"{table_name} ... 空表")
                except Exception as e:
                    self.add_log("WARN", f"{table_name} ... 读取失败: {e}")
            else:
                if required:
                    missing_required.append(table_name)
                    self.add_log("ERROR", f"{table_name} ... 缺失 (必需)")
                else:
                    self.add_log("WARN", f"{table_name} ... 缺失 (可选)")
        
        if missing_required:
            self.set_error(ErrorCode.ERR_DATA_MISSING, 
                          f"必需数据表缺失: {', '.join(missing_required)}")
            return False
        
        # 检查数据新鲜度并自动更新
        if self.auto_update_enabled:
            needs_update, data_latest, today = self._check_data_freshness()
            
            if needs_update and data_latest:
                # 计算更新范围：从数据最新日期的下一天到今天
                from datetime import datetime, timedelta
                
                try:
                    start = datetime.strptime(data_latest, "%Y%m%d") + timedelta(days=1)
                    end = datetime.strptime(today, "%Y%m%d")
                    
                    # 确保开始日期不晚于结束日期
                    if start <= end:
                        start_str = start.strftime("%Y%m%d")
                        end_str = end.strftime("%Y%m%d")
                        
                        update_success = self._run_data_update(start_str, end_str)
                        
                        if not update_success:
                            # 更新失败但不阻断启动，记录警告
                            self.add_log("WARN", "数据更新失败，将使用现有数据继续启动")
                    else:
                        self.add_log("INFO", "数据已是最新，无需更新")
                except Exception as e:
                    self.add_log("WARN", f"计算更新范围失败: {e}")
            elif needs_update and not data_latest:
                # 无法获取最新日期，尝试全量更新
                self.add_log("WARN", "无法确定数据日期，尝试更新最近5天数据")
                from datetime import datetime, timedelta
                end = datetime.strptime(today, "%Y%m%d")
                start = end - timedelta(days=5)
                self._run_data_update(start.strftime("%Y%m%d"), today)
        else:
            self.add_log("INFO", "自动数据更新已禁用")
        
        return True
    
    def _get_parquet_row_count(self, file_path: Path) -> int:
        """获取 Parquet 文件行数"""
        try:
            import polars as pl
            df = pl.scan_parquet(str(file_path)).select(pl.len()).collect()
            return df.item() if df.height > 0 else 0
        except Exception:
            return 0
    
    def _get_data_latest_date(self) -> Optional[str]:
        """获取数据的最新日期"""
        try:
            from server.app import get_global_data_query
            data_query = get_global_data_query()
            dates = data_query.get_trading_dates()
            if dates:
                return dates[-1]
        except Exception as e:
            self.add_log("WARN", f"获取数据最新日期失败: {e}")
        return None
    
    def _get_today_date(self) -> str:
        """获取今天的日期（考虑交易日）"""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d")
    
    def _is_trading_day(self, date_str: str) -> bool:
        """检查指定日期是否为交易日"""
        try:
            import polars as pl
            
            parquet_dir = Path(Config.PARQUET_DIR)
            benchmark_file = parquet_dir / "benchmark_daily.parquet"
            
            if not benchmark_file.exists():
                return True
            
            df = pl.scan_parquet(str(benchmark_file)).filter(
                pl.col("trade_date") == date_str
            ).select(pl.len()).collect()
            
            return df.item() > 0 if df.height > 0 else False
        except Exception:
            return True
    
    def _check_data_freshness(self) -> tuple[bool, Optional[str], Optional[str]]:
        """
        检查数据新鲜度
        
        Returns:
            (是否需要更新, 数据最新日期, 今天日期)
        """
        data_latest = self._get_data_latest_date()
        today = self._get_today_date()
        
        if not data_latest:
            self.add_log("WARN", "无法获取数据最新日期，将尝试更新数据")
            return True, None, today
        
        # 如果数据已经是最新的，不需要更新
        if data_latest >= today:
            self.add_log("INFO", f"数据已是最新: {data_latest}")
            return False, data_latest, today
        
        # 检查今天是否为交易日
        if not self._is_trading_day(today):
            self.add_log("INFO", f"今天({today})非交易日，数据日期 {data_latest} 已足够新")
            return False, data_latest, today
        
        # 数据需要更新
        self.add_log("INFO", f"数据需要更新: 最新 {data_latest}, 今天 {today}")
        return True, data_latest, today
    
    def _run_data_update(self, start_date: str, end_date: str) -> bool:
        """
        执行数据更新（后台异步，不阻塞启动）
        
        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            更新是否成功启动
        """
        self.update_status("integrity", "updating_data", f"正在后台更新数据 ({start_date} ~ {end_date})...", 35)
        self.add_log("INFO", f"启动后台数据更新: {start_date} ~ {end_date}")
        
        def _background_update():
            """后台更新线程"""
            try:
                from data_svc.storage.unified_updater import UnifiedDataUpdater
                
                def progress_callback(data):
                    """进度回调，记录日志但不更新状态（避免干扰启动流程）"""
                    self.add_log("INFO", f"[Update] {data.get('status')} - {data.get('message')}")
                
                updater = UnifiedDataUpdater(progress_callback=progress_callback)
                result = updater.run_full_update(
                    start_date=start_date,
                    end_date=end_date,
                    skip_factors=True
                )
                
                if result.success:
                    self.add_log("INFO", f"后台数据更新完成: {result.message}")
                else:
                    self.add_log("WARN", f"后台数据更新失败: {result.message}")
                    
            except Exception as e:
                self.add_log("ERROR", f"后台数据更新异常: {e}")
        
        # 启动后台更新线程
        update_thread = threading.Thread(target=_background_update, daemon=True)
        update_thread.start()
        
        # 不等待更新完成，直接返回 True 让启动流程继续
        self.add_log("INFO", "数据更新已在后台启动，系统将继续启动流程")
        return True
    
    def check_kernel(self) -> bool:
        """
        Phase 3: 内核初始化
        - 策略工厂初始化
        - 数据查询引擎预热
        """
        self.update_status("kernel", "loading_strategies", "正在加载策略模块...", 70)
        
        try:
            from core.strategies.strategy_factory import get_factory
            factory = get_factory()
            strategies = factory.list_strategies()
            self.add_log("INFO", f"策略工厂 ... 已加载 {len(strategies)} 个策略")
        except Exception as e:
            self.set_error(ErrorCode.ERR_KERNEL_INIT, f"策略工厂初始化失败: {e}")
            return False
        
        self.update_status("kernel", "warming_cache", "正在预热数据缓存...", 85)
        
        try:
            from server.app import get_global_data_query
            data_query = get_global_data_query()
            dates = data_query.get_trading_dates()
            if dates:
                self.add_log("INFO", f"数据引擎 ... 预热完成，最近交易日: {dates[-1]}")
            else:
                self.add_log("WARN", "数据引擎 ... 预热完成，但未找到交易日数据")
        except Exception as e:
            self.add_log("WARN", f"数据引擎预热警告: {e}")
        
        return True
    
    def run_startup_checks(self):
        """执行完整的启动检查流程"""
        if self._is_running:
            return
        
        self._is_running = True
        self.status = StartupStatus()
        
        self.add_log("INFO", "AquaTrade 启动检查开始...")
        
        if not self.check_environment():
            self._is_running = False
            return
        
        if not self.check_integrity():
            self._is_running = False
            return
        
        if not self.check_kernel():
            self._is_running = False
            return
        
        self.update_status("ready", "complete", "系统就绪", 100)
        self.status.ready = True
        self.add_log("INFO", "AquaTrade 启动检查完成，系统就绪")
        
        self._is_running = False
        
        # 启动每日定时更新检查
        if self.daily_update_enabled:
            self._schedule_daily_update()
    
    def _schedule_daily_update(self):
        """
        调度每日数据更新检查
        
        在指定时间（默认早上9点）检查是否需要更新数据
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        target_time = now.replace(hour=self.daily_update_hour, minute=0, second=0, microsecond=0)
        
        # 如果目标时间已过，设置为明天
        if target_time <= now:
            target_time = target_time + timedelta(days=1)
        
        # 计算等待秒数
        wait_seconds = (target_time - now).total_seconds()
        
        self.add_log("INFO", f"下次数据更新检查: {target_time.strftime('%Y-%m-%d %H:%M:%S')} ({int(wait_seconds)}秒后)")
        
        def _check_and_update():
            """检查并执行每日更新"""
            today = datetime.now().strftime("%Y%m%d")
            
            # 检查今天是否已经更新过
            if self._last_update_date == today:
                self.add_log("INFO", f"今日({today})已更新过数据，跳过")
            else:
                self.add_log("INFO", f"开始每日数据更新检查: {today}")
                self._run_background_update()
                self._last_update_date = today
            
            # 重新调度下一次更新（24小时后）
            if self.daily_update_enabled:
                self._daily_update_timer = threading.Timer(24 * 3600, _check_and_update)
                self._daily_update_timer.daemon = True
                self._daily_update_timer.start()
        
        # 启动定时器
        self._daily_update_timer = threading.Timer(wait_seconds, _check_and_update)
        self._daily_update_timer.daemon = True
        self._daily_update_timer.start()
    
    def _run_background_update(self):
        """执行后台数据更新（无感更新）"""
        from datetime import datetime, timedelta
        
        today = datetime.now().strftime("%Y%m%d")
        
        def _update_task():
            try:
                from data_svc.storage.unified_updater import UnifiedDataUpdater
                
                def progress_callback(data):
                    """进度回调，只记录日志"""
                    self.add_log("INFO", f"[DailyUpdate] {data.get('status')} - {data.get('message')}")
                
                updater = UnifiedDataUpdater(progress_callback=progress_callback)
                result = updater.run_full_update(skip_factors=True)
                
                if result.success:
                    self.add_log("INFO", f"每日数据更新完成: {result.message}")
                else:
                    self.add_log("WARN", f"每日数据更新失败: {result.message}")
                    
            except Exception as e:
                self.add_log("ERROR", f"每日数据更新异常: {e}")
        
        # 启动后台更新线程
        update_thread = threading.Thread(target=_update_task, daemon=True)
        update_thread.start()
    
    def start_async(self):
        """异步启动检查"""
        if self._startup_thread and self._startup_thread.is_alive():
            return
        
        self._startup_thread = threading.Thread(target=self.run_startup_checks, daemon=True)
        self._startup_thread.start()
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self.status.to_dict()
    
    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self.status.ready
    
    def has_error(self) -> bool:
        """检查是否有错误"""
        return self.status.error_code is not None
    
    def stop(self):
        """停止所有后台任务"""
        if self._daily_update_timer:
            self._daily_update_timer.cancel()
            self._daily_update_timer = None
        self.add_log("INFO", "启动服务已停止")


_startup_service: Optional[StartupService] = None


def get_startup_service() -> StartupService:
    """获取启动服务单例"""
    global _startup_service
    if _startup_service is None:
        _startup_service = StartupService()
    return _startup_service
