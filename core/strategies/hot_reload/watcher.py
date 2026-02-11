"""
文件监听器 - 监听策略文件变化并触发重载

使用 watchdog 库监听文件系统事件
"""

import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from .loader import StrategyLoader

logger = logging.getLogger(__name__)


class StrategyFileHandler(FileSystemEventHandler):
    """策略文件变化处理器"""
    
    def __init__(self, debounce_seconds: float = 1.0):
        """
        初始化
        
        参数：
            debounce_seconds: 防抖延迟（秒），避免频繁重载
        """
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self._last_reload_time = {}  # {file_path: timestamp}
    
    def on_modified(self, event):
        """文件修改事件"""
        if event.is_directory:
            return
        
        # 只处理 Python 文件
        if not event.src_path.endswith('.py'):
            return
        
        # 排除 __pycache__ 和 __init__.py
        if '__pycache__' in event.src_path or event.src_path.endswith('__init__.py'):
            return
        
        file_path = event.src_path
        
        # 防抖：避免短时间内多次触发
        current_time = time.time()
        last_reload = self._last_reload_time.get(file_path, 0)
        
        if current_time - last_reload < self.debounce_seconds:
            logger.debug(f"防抖跳过: {file_path}")
            return
        
        self._last_reload_time[file_path] = current_time
        
        # 触发重载
        logger.info(f"🔔 检测到文件变化: {file_path}")
        
        try:
            StrategyLoader.reload_by_path(file_path)
            logger.info(f"✅ 自动重载成功: {file_path}")
        except Exception as e:
            logger.error(f"❌ 自动重载失败: {file_path}, 错误: {e}")


class StrategyWatcher:
    """策略文件监听器"""
    
    def __init__(
        self,
        watch_dir: str = None,
        debounce_seconds: float = 1.0,
        recursive: bool = False
    ):
        """
        初始化监听器
        
        参数：
            watch_dir: 监听目录（默认 = strategies/）
            debounce_seconds: 防抖延迟
            recursive: 是否递归监听子目录
        """
        if watch_dir is None:
            # 默认监听 strategies 目录
            watch_dir = str(Path(__file__).parent.parent)
        
        self.watch_dir = watch_dir
        self.debounce_seconds = debounce_seconds
        self.recursive = recursive
        
        # 创建观察者
        self.observer = Observer()
        self.handler = StrategyFileHandler(debounce_seconds=debounce_seconds)
        
        # 是否正在运行
        self._running = False
    
    def start(self):
        """启动监听器"""
        if self._running:
            logger.warning("监听器已在运行")
            return
        
        # 注册路径监听
        self.observer.schedule(
            self.handler,
            self.watch_dir,
            recursive=self.recursive
        )
        
        # 启动观察者线程
        self.observer.start()
        self._running = True
        
        logger.info(f"👁️  策略文件监听器已启动: {self.watch_dir}")
        logger.info(f"   防抖延迟: {self.debounce_seconds}s")
        logger.info(f"   递归监听: {self.recursive}")
    
    def stop(self):
        """停止监听器"""
        if not self._running:
            return
        
        self.observer.stop()
        self.observer.join(timeout=5)
        self._running = False
        
        logger.info("🛑 策略文件监听器已停止")
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


# 全局单例
_watcher_instance = None

def get_watcher(auto_start: bool = False) -> StrategyWatcher:
    """获取全局监听器实例"""
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = StrategyWatcher()
        if auto_start:
            _watcher_instance.start()
    return _watcher_instance
