"""
策略加载器 - 动态加载和重载策略类

功能：
1. 动态导入策略模块
2. 安全的 importlib.reload
3. 策略实例缓存
"""

import importlib
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from .config_manager import get_config_manager

logger = logging.getLogger(__name__)


class StrategyLoader:
    """策略动态加载器"""
    
    # 策略模块路径映射 {strategy_id: module_path}
    STRATEGY_MAP = {
        "jq_volume_v1pro": "core.strategies.jq_volume_strategy_v2",
        # 可以添加更多策略映射
    }
    
    # 策略缓存 {strategy_id: (module, class, instance)}
    _cache: Dict[str, tuple] = {}
    
    @classmethod
    def get_module_path(cls, strategy_id: str) -> Optional[str]:
        """获取策略模块路径"""
        return cls.STRATEGY_MAP.get(strategy_id)
    
    @classmethod
    def load_strategy(
        cls,
        strategy_id: str,
        config: Optional[Dict] = None,
        force_reload: bool = False
    ):
        """
        加载策略（动态导入+配置化）
        
        参数：
            strategy_id: 策略ID
            config: 配置参数（None = 从配置文件加载）
            force_reload: 是否强制重载
        
        返回：
            策略实例
        """
        # 1. 获取模块路径
        module_path = cls.get_module_path(strategy_id)
        if not module_path:
            raise ValueError(f"未知策略ID: {strategy_id}")
        
        # 2. 检查缓存
        if not force_reload and strategy_id in cls._cache:
            logger.debug(f"从缓存加载策略: {strategy_id}")
            _, strategy_class, _ = cls._cache[strategy_id]
        else:
            # 3. 动态导入模块
            try:
                if module_path in sys.modules and force_reload:
                    # 重载模块
                    logger.info(f"🔄 重载模块: {module_path}")
                    module = importlib.reload(sys.modules[module_path])
                else:
                    # 首次导入
                    logger.info(f"📦 导入模块: {module_path}")
                    module = importlib.import_module(module_path)
            except Exception as e:
                logger.error(f"导入模块失败: {module_path}, 错误: {e}")
                raise
            
            # 4. 提取策略类
            strategy_class = cls._extract_strategy_class(module)
            if not strategy_class:
                raise ValueError(f"模块中未找到策略类: {module_path}")
        
        # 5. 加载配置
        if config is None:
            config_manager = get_config_manager()
            config = config_manager.load_config(strategy_id)
        
        # 6. 实例化策略
        try:
            if config:
                # 检查策略类是否有 config 属性（dataclass）
                # 注意：这里需要检查策略类定义中使用的 config 类型
                if hasattr(strategy_class, '__annotations__'):
                    # 尝试从策略模块获取配置类
                    # 例如：JQVolumeStrategypro 使用 JQVolumeConfigpro
                    import inspect
                    module = inspect.getmodule(strategy_class)
                    
                    # 查找配置类（通常命名为 StrategyNameConfig）
                    config_class = None
                    for name, obj in inspect.getmembers(module):
                        if name.endswith('Config') or name.endswith('Configpro'):
                            if inspect.isclass(obj) and hasattr(obj, '__dataclass_fields__'):
                                config_class = obj
                                break
                    
                    if config_class:
                        # 使用配置类创建实例
                        logger.debug(f"使用配置类: {config_class.__name__}")
                        config_instance = config_class(**config)
                        strategy_instance = strategy_class(config=config_instance)
                    else:
                        # Fallback: 直接传递配置字典
                        strategy_instance = strategy_class(config=config)
                else:
                    # 没有类型注解，直接传递配置
                    strategy_instance = strategy_class(**config)
            else:
                # 使用默认值
                strategy_instance = strategy_class()
            
            # 7. 缓存
            cls._cache[strategy_id] = (module, strategy_class, strategy_instance)
            
            logger.info(f"✅ 策略加载成功: {strategy_id}")
            return strategy_instance
            
        except Exception as e:
            logger.error(f"策略实例化失败: {strategy_id}, 错误: {e}")
            raise
    
    @classmethod
    def reload_strategy(cls, strategy_id: str, config: Optional[Dict] = None):
        """
        热重载策略（用于文件变更后）
        
        参数：
            strategy_id: 策略ID
            config: 新配置（None = 从配置文件加载）
        
        返回：
            新的策略实例
        """
        logger.info(f"🔥 热重载策略: {strategy_id}")
        
        # 清除缓存
        cls._cache.pop(strategy_id, None)
        
        # 清除配置缓存
        config_manager = get_config_manager()
        config_manager.clear_cache(strategy_id)
        
        # 重新加载
        return cls.load_strategy(strategy_id, config=config, force_reload=True)
    
    @classmethod
    def reload_by_path(cls, file_path: str):
        """
        根据文件路径重载策略
        
        参数：
            file_path: 策略文件路径
        """
        # 将文件路径转换为策略ID
        strategy_id = cls._path_to_strategy_id(file_path)
        if strategy_id:
            cls.reload_strategy(strategy_id)
        else:
            logger.debug(f"无法识别策略文件（非热重载策略）: {file_path}")
    
    @classmethod
    def _extract_strategy_class(cls, module):
        """
        从模块中提取策略类
        
        策略类的特征：
        1. 继承自 StrategyBase 或 VectorizedStrategyBase
        2. 有 strategy_id 属性
        """
        from core.strategies.strategy_framework import StrategyBase
        from core.strategies.vectorized_base import VectorizedStrategyBase
        
        for name in dir(module):
            obj = getattr(module, name)
            
            # 检查是否是类
            if not isinstance(obj, type):
                continue
            
            # 检查是否继承自策略基类
            if issubclass(obj, (StrategyBase, VectorizedStrategyBase)):
                # 排除基类本身
                if obj not in (StrategyBase, VectorizedStrategyBase):
                    return obj
        
        return None
    
    @classmethod
    def _path_to_strategy_id(cls, file_path: str) -> Optional[str]:
        """
        文件路径 → 策略ID
        
        例如：d:\\aquatrade\\core\\strategies\\jq_volume_strategy_v2.py
             → jq_volume_v1pro (查找映射表)
        """
        file_path = Path(file_path)
        module_name_from_file = file_path.stem  # 例如 jq_volume_strategy_v2
        
        # 在映射表中查找
        for strategy_id, module_path in cls.STRATEGY_MAP.items():
            if module_name_from_file in module_path:
                return strategy_id
        
        return None
    
    @classmethod
    def register_strategy(cls, strategy_id: str, module_path: str):
        """注册新策略映射"""
        cls.STRATEGY_MAP[strategy_id] = module_path
        logger.info(f"注册策略: {strategy_id} -> {module_path}")
    
    @classmethod
    def list_strategies(cls) -> list[str]:
        """列出所有注册的策略"""
        return list(cls.STRATEGY_MAP.keys())
