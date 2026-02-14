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
        
        self.required_parquet_files = [
            ("base_daily_hot.parquet", True, "K线数据"),
            ("stock_info.parquet", True, "股票信息"),
            ("benchmark_daily.parquet", False, "基准数据"),
            ("guba_posts.parquet", False, "股吧舆情"),
        ]
    
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
        - Parquet 文件存在性
        - 文件大小校验
        """
        self.update_status("integrity", "checking_parquet", "正在校验数据文件...", 30)
        
        parquet_dir = Path(Config.PARQUET_DIR)
        
        if not parquet_dir.exists():
            self.set_error(ErrorCode.ERR_DATA_MISSING, f"数据目录不存在: {parquet_dir}")
            return False
        
        missing_required = []
        
        for i, (filename, required, description) in enumerate(self.required_parquet_files):
            file_path = parquet_dir / filename
            progress = 30 + int((i + 1) / len(self.required_parquet_files) * 30)
            self.update_status("integrity", f"checking_{filename}", 
                             f"正在检查 {description}...", progress)
            
            if file_path.exists():
                file_size = file_path.stat().st_size
                if file_size < 1024:
                    self.add_log("WARN", f"{filename} ... 文件过小 ({file_size} bytes)")
                else:
                    size_mb = file_size / (1024 * 1024)
                    row_count = self._get_parquet_row_count(file_path)
                    if row_count > 0:
                        self.add_log("INFO", f"{filename} ... {size_mb:.1f}MB, {row_count:,} rows")
                    else:
                        self.add_log("INFO", f"{filename} ... {size_mb:.1f}MB")
            else:
                if required:
                    missing_required.append(filename)
                    self.add_log("ERROR", f"{filename} ... 缺失 (必需)")
                else:
                    self.add_log("WARN", f"{filename} ... 缺失 (可选)")
        
        if missing_required:
            self.set_error(ErrorCode.ERR_DATA_MISSING, 
                          f"必需数据文件缺失: {', '.join(missing_required)}")
            return False
        
        return True
    
    def _get_parquet_row_count(self, file_path: Path) -> int:
        """获取 Parquet 文件行数"""
        try:
            import duckdb
            con = duckdb.connect()
            result = con.execute(f"SELECT COUNT(*) FROM read_parquet('{str(file_path)}')").fetchone()
            con.close()
            return result[0] if result else 0
        except Exception:
            return 0
    
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
            from data_svc.database.optimized_data_query import OptimizedStockDataQuery
            data_query = OptimizedStockDataQuery(warmup=True)
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


_startup_service: Optional[StartupService] = None


def get_startup_service() -> StartupService:
    """获取启动服务单例"""
    global _startup_service
    if _startup_service is None:
        _startup_service = StartupService()
    return _startup_service
