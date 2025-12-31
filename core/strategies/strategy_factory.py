# strategies/strategy_factory.py
"""策略工厂 - 自动发现并注册所有继承自 StrategyBase 的策略类。

特性：
- 自动扫描 strategies 目录（优先 *_strategy.py）
- 自动注册声明了 strategy_id / strategy_name 的策略类
- 向后兼容 create_strategy / get_available_strategies / list_strategies 等旧接口
"""

import inspect
import importlib
import os
import pkgutil
import sys
from typing import Any, Dict, List, Optional, Type

from core.strategies.strategy_framework import StrategyBase


class StrategyFactory:
    """策略工厂 - 自动扫描并注册策略类"""

    def __init__(self) -> None:
        # registry 统一使用 strategy_id 作为 key
        self.registry: Dict[str, Type[StrategyBase]] = {}
        self._id_to_name: Dict[str, str] = {}  # strategy_id -> strategy_name
        self._name_to_id: Dict[str, str] = {}  # strategy_name -> strategy_id

        self._strategies_path = os.path.dirname(__file__)
        self._strategies_mtime = 0.0
        self._discover_strategies(force_reload=True)
    
    def _discover_strategies(self, force_reload: bool = False) -> None:
        """自动发现所有继承自 StrategyBase 的策略类。"""
        from config.logger import get_logger
        logger = get_logger(__name__)
        debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
        
        if debug_mode:
            logger.debug(f"开始扫描策略目录: {self._strategies_path}")

        self.registry.clear()
        self._id_to_name.clear()
        self._name_to_id.clear()

        # 获取当前的 StrategyBase（在重新加载前）
        current_strategy_base = StrategyBase
        
        if force_reload and "core.strategies.strategy_framework" in sys.modules:
            if debug_mode:
                logger.debug("重新加载 strategy_framework 模块以保持类身份一致")
            importlib.reload(sys.modules["core.strategies.strategy_framework"])
            # 重新加载后，更新 StrategyBase 引用
            from core.strategies.strategy_framework import StrategyBase as ReloadedStrategyBase
            current_strategy_base = ReloadedStrategyBase

        modules = list(pkgutil.iter_modules([self._strategies_path]))
        modules.sort(key=lambda item: item[1])  # 稳定顺序
        if debug_mode:
            logger.debug(f"找到 {len(modules)} 个模块候选")

        for loader, module_name, is_pkg in modules:
            if is_pkg or module_name.startswith("_"):
                if debug_mode:
                    logger.debug(f"跳过: {module_name} (是包或以下划线开头)")
                continue

            module_full_name = f"core.strategies.{module_name}"

            try:
                if force_reload and module_full_name in sys.modules:
                    module = importlib.reload(sys.modules[module_full_name])
                else:
                    module = importlib.import_module(module_full_name)
            except Exception as e:
                logger.error(f"导入模块 {module_full_name} 时出错: {e}", exc_info=True)
                continue

            classes = list(inspect.getmembers(module, inspect.isclass))
            if debug_mode:
                logger.debug(f"在模块 {module_name} 中找到 {len(classes)} 个类")

            for name, obj in classes:
                # 只检查模块内定义的类
                if getattr(obj, '__module__', None) != module.__name__:
                    continue
                
                # 使用当前的 StrategyBase 进行检查（可能是重新加载后的版本）
                try:
                    is_subclass = (obj is not current_strategy_base 
                                   and issubclass(obj, current_strategy_base))
                except (TypeError, AttributeError):
                    # 如果 issubclass 检查失败，跳过
                    continue
                
                if is_subclass:
                    self._register_strategy_instance(obj)

        if debug_mode:
            logger.debug(f"策略扫描完成，共注册 {len(self.registry)} 个策略")
            for sid, cls in self.registry.items():
                logger.debug(
                    f"已注册策略: {sid} "
                    f"({self._id_to_name.get(sid, sid)}) -> {cls.__module__}.{cls.__name__}"
                )
        self._strategies_mtime = self._get_latest_mtime()

    def _register_strategy_instance(self, strategy_class: Type[StrategyBase]) -> None:
        """根据 strategy_id / strategy_name 规则注册单个策略类。"""
        module_name = strategy_class.__module__
        class_name = strategy_class.__name__

        raw_id: Any = getattr(strategy_class, "strategy_id", None)
        raw_name: Any = getattr(strategy_class, "strategy_name", None)

        if not isinstance(raw_name, str) or not raw_name.strip():
            raw_name = raw_id if isinstance(raw_id, str) and raw_id.strip() else class_name
        if not isinstance(raw_id, str) or not raw_id.strip():
            raw_id = raw_name

        strategy_id = str(raw_id).strip() or class_name
        strategy_name = str(raw_name).strip() or strategy_id

        if strategy_id in self.registry:
            existing = self.registry[strategy_id]
            from config.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(
                f"跳过重复的 strategy_id '{strategy_id}': "
                f"{module_name}.{class_name} 已被 "
                f"{existing.__module__}.{existing.__name__} 占用"
            )
            return

        self.registry[strategy_id] = strategy_class
        self._id_to_name[strategy_id] = strategy_name
        if strategy_name not in self._name_to_id:
            self._name_to_id[strategy_name] = strategy_id

        # 只在 DEBUG 模式下输出注册信息
        debug_mode = os.getenv('LOG_LEVEL', '').upper() == 'DEBUG'
        if debug_mode:
            from config.logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"自动注册策略: {strategy_id} -> {module_name}.{class_name}")

    def _get_latest_mtime(self) -> float:
        latest = 0.0
        for entry in os.scandir(self._strategies_path):
            if (
                entry.is_file()
                and entry.name.endswith(".py")
                and not entry.name.startswith("_")
            ):
                try:
                    latest = max(latest, entry.stat().st_mtime)
                except OSError:
                    continue
        return latest

    def _auto_refresh_registry(self) -> None:
        latest = self._get_latest_mtime()
        if latest > self._strategies_mtime:
            print("[StrategyFactory] 检测到策略文件更新，自动热重载中...")
            self._discover_strategies(force_reload=True)
    
    def _create_strategy_instance(
        self,
        strategy_identifier: str,
        use_simple: bool = True,
        *args,
        **kwargs,
    ) -> StrategyBase:
        """创建策略实例（支持 strategy_id / strategy_name / 旧 ID）。"""
        sid = self._resolve_identifier_to_id(strategy_identifier)
        if not sid:
            available = ", ".join(sorted(self.registry.keys()))
            raise ValueError(
                f"未找到策略：'{strategy_identifier}'。\n可用策略 ID：{available}"
            )

        strategy_class = self.registry.get(sid)
        if strategy_class is None:
            available = ", ".join(sorted(self.registry.keys()))
            raise ValueError(
                f"未找到策略：'{strategy_identifier}'（解析为 ID: '{sid}'）。\n可用策略 ID：{available}"
            )

        # 检查策略构造函数是否只接受 config 参数
        import inspect
        sig = inspect.signature(strategy_class.__init__)
        params = list(sig.parameters.keys())
        
        # 如果策略只接受 config 参数（除了 self），并且传入了其他参数
        if len(params) == 2 and 'config' in params and kwargs:
            # 检查是否有 JQVolumeConfig 类
            try:
                from core.strategies.jq_volume_strategy import JQVolumeConfig
                from dataclasses import replace
                
                # 创建默认配置对象
                config = JQVolumeConfig()
                # 使用 replace 创建新的配置对象，替换指定的参数
                config_fields = {}
                for key, value in kwargs.items():
                    if hasattr(config, key):
                        config_fields[key] = value
                
                if config_fields:
                    config = replace(config, **config_fields)
                    print(f"[DEBUG] 为策略 {strategy_class.__name__} 创建配置对象，参数: {config_fields}")
                else:
                    print(f"[DEBUG] 为策略 {strategy_class.__name__} 使用默认配置对象")
                
                return strategy_class(config=config)
            except ImportError:
                print(f"[DEBUG] 无法导入 JQVolumeConfig，使用默认参数创建策略")
                return strategy_class(*args, **kwargs)
        
        return strategy_class(*args, **kwargs)

    def _resolve_identifier_to_id(self, identifier: str) -> Optional[str]:
        """把旧 ID / 中文名 / 新 ID 统一解析为内部 strategy_id。"""
        self._auto_refresh_registry()

        if identifier in self.registry:
            return identifier
        if identifier in self._name_to_id:
            return self._name_to_id[identifier]

        legacy_mapping = {
            "jq_volume": "聚宽量比市值策略",
            "volume": "量价策略",
            "breakout": "突破策略",
            "mean_reversion": "均值回归策略",
        }
        if identifier in legacy_mapping:
            name = legacy_mapping[identifier]
            return self._name_to_id.get(name)
        return None

    def _get_available_strategies_instance(self) -> Dict[str, str]:
        self._auto_refresh_registry()
        strategies = {
            sid: self._id_to_name.get(sid, sid)
            for sid in sorted(self.registry.keys())
        }
        print(f"[DEBUG] 返回可用策略列表: {list(strategies.keys())}")
        return strategies

    def _get_strategy_by_name_instance(
        self, strategy_name: str
    ) -> Optional[Type[StrategyBase]]:
        self._auto_refresh_registry()
        sid = self._name_to_id.get(strategy_name)
        if not sid and strategy_name in self.registry:
            sid = strategy_name
        return self.registry.get(sid) if sid else None

    def _get_strategy_by_id_instance(self, strategy_id: str) -> Optional[Type[StrategyBase]]:
        self._auto_refresh_registry()
        return self.registry.get(strategy_id)

    def _list_strategies_instance(self) -> List[Dict[str, Any]]:
        self._auto_refresh_registry()
        result: List[Dict[str, Any]] = []
        for sid, cls in sorted(self.registry.items()):
            result.append(
                {
                    "id": sid,
                    "name": self._id_to_name.get(sid, sid),
                    "class_name": cls.__name__,
                    "module": cls.__module__,
                }
            )
        print(f"[DEBUG] list_strategies 返回 {len(result)} 个策略信息")
        return result

    # 保留实例方法接口，便于直接调用
    def create_strategy(self, strategy_name: str, use_simple: bool = True, *args, **kwargs) -> StrategyBase:
        return self._create_strategy_instance(strategy_name, use_simple, *args, **kwargs)
    
    def get_available_strategies(self) -> Dict[str, str]:
        """获取可用策略列表（向后兼容）。"""
        return self._get_available_strategies_instance()

    def get_strategy_by_name(
        self, strategy_name: str
    ) -> Optional[Type[StrategyBase]]:
        """根据“策略名称”（中文名）获取策略类（向后兼容）。"""
        return self._get_strategy_by_name_instance(strategy_name)

    def get_strategy_by_id(self, strategy_id: str) -> Optional[Type[StrategyBase]]:
        """根据 strategy_id 获取策略类。"""
        return self._get_strategy_by_id_instance(strategy_id)

    def list_strategies(self) -> list:
        """列出所有可用的策略，返回更详细的策略信息。"""
        return self._list_strategies_instance()


_factory_instance: Optional[StrategyFactory] = None


def _get_factory_static(cls):
    """获取策略工厂实例"""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = StrategyFactory()
    return _factory_instance


# 添加类方法到 StrategyFactory
StrategyFactory.get_factory = classmethod(_get_factory_static)


def get_factory() -> StrategyFactory:
    """获取策略工厂单例"""
    return StrategyFactory.get_factory()


# 向后兼容：在类上添加静态方法（保持旧 API 兼容）
# 注意：这些方法不会覆盖实例方法，因为 Python 的方法解析顺序会优先使用实例方法
@staticmethod
def _create_strategy_static(strategy_type: str, use_simple: bool = True, *args, **kwargs):
    """
    向后兼容的静态方法（已废弃，建议使用 get_factory().create_strategy）
    """
    factory = get_factory()
    return factory._create_strategy_instance(strategy_type, use_simple, *args, **kwargs)


@staticmethod
def _get_available_strategies_static():
    """
    向后兼容的静态方法（已废弃，建议使用 get_factory().get_available_strategies）
    """
    factory = get_factory()
    return factory._get_available_strategies_instance()


# 为了向后兼容，添加静态方法到类
# 使用描述符确保不会覆盖实例方法
StrategyFactory.create_strategy = _create_strategy_static
StrategyFactory.get_available_strategies = _get_available_strategies_static
