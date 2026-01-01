"""
策略服务
负责策略相关的业务逻辑
"""
from typing import Dict, List, Any
from core.strategies.strategy_factory import StrategyFactory
from dataclasses import is_dataclass, asdict, fields


class StrategyService:
    """策略服务类"""
    
    def get_strategy_list(self) -> List[Dict]:
        """获取策略列表（不需要数据库连接）"""
        strategies = []
        try:
            # 直接导入并使用get_factory函数
            from core.strategies.strategy_factory import get_factory
            
            factory = get_factory()
            
            # 使用list_strategies方法获取更详细的策略信息
            strategy_info_list = factory.list_strategies()
            
            # 确保strategy_info_list是列表类型
            if not isinstance(strategy_info_list, list):
                print(f"[ERROR] 策略工厂返回的不是列表，而是: {type(strategy_info_list)}")
                return []
            
            for idx, strategy_info in enumerate(strategy_info_list):
                # 安全地获取策略信息
                strategy_id = strategy_info.get('name', '')
                class_name = strategy_info.get('class_name', '')
                
                # 如果name为空，尝试使用class_name
                if not strategy_id and class_name:
                    strategy_id = class_name
                
                if not strategy_id:
                    continue
                
                strategy_name = strategy_id  # 使用名称作为ID和名称
                
                # 创建策略字典并添加到结果列表
                strategy_dict = {
                    "id": strategy_id,
                    "name": strategy_name,
                    "description": f"{strategy_name}的描述",
                    "createdDate": "2024-01-01",
                    "lastUpdated": "2024-01-01",
                    "performance": 0.0,
                    "status": "active"
                }
                strategies.append(strategy_dict)
            
            return strategies
        except Exception as e:
            print(f"[ERROR] 获取策略列表失败: {e}")
            import traceback
            traceback.print_exc()
            return []  # 返回空列表而不是报错
    
    def get_strategy_logic(self, strategy_id: str) -> Dict[str, Any]:
        """
        获取策略的逻辑描述
        【优化】直接读取策略类的 DocString，不再维护硬编码字典
        """
        try:
            strategy_class = StrategyFactory.get_factory().get_strategy_by_name(strategy_id)
            if not strategy_class:
                return {"buy_logic": "策略未找到", "sell_logic": "", "description": ""}
            
            # 1. 优先尝试调用策略类的 get_logic_description 方法 (如果你实现了的话)
            if hasattr(strategy_class, "get_logic_description"):
                return strategy_class.get_logic_description()

            # 2. 否则自动解析 Python 文档注释 (__doc__)
            doc = strategy_class.__doc__ or "暂无描述"
            
            # 简单粗暴的解析：假设文档里写了 "买入逻辑：" 和 "卖出逻辑："
            # 如果没写，就全部丢给 description
            return {
                "buy_logic": "请在策略代码类注释中补充买入逻辑...", # 前端兼容占位
                "sell_logic": "请在策略代码类注释中补充卖出逻辑...", 
                "description": doc.strip()
            }
        except Exception as e:
            print(f"获取策略逻辑失败: {e}")
            return {"buy_logic": "获取失败", "sell_logic": "", "description": ""}
    
    def get_strategy_params(self, strategy_id: str) -> list[dict]:
        """
        返回给前端用的参数列表。
        【优化】彻底移除 param_metadata 映射和 default_min/max 猜测逻辑。
        只有策略类明确说了范围 (get_param_spec) 才返回，否则一律 None，由前端接管。
        """
        # 1. 找到策略类
        strategy_class = StrategyFactory.get_factory().get_strategy_by_name(strategy_id)
        if strategy_class is None:
            raise ValueError(f"未找到策略：{strategy_id}")

        # 2. 优先使用策略类提供的 PARAM_SPEC
        if hasattr(strategy_class, "get_param_spec"):
            spec = strategy_class.get_param_spec()
            if spec:
                # 完全放权给前端：不返回 min/max，让前端自主决定搜索范围
                return [
                    {
                        "key": item["key"],
                        "label": item.get("label", item["key"]),
                        "group": item.get("group", "其它"),
                        "type": item.get("type", "float"),
                        "min": None,  # 不返回范围限制，完全由前端控制
                        "max": None,  # 不返回范围限制，完全由前端控制
                        "step": item.get("step"),
                        "default": item.get("default"),
                        "optimize": item.get("optimize", True),
                        "description": item.get("description", ""),
                    }
                    for item in spec
                ]

        # 3. 退回 dataclass 自动推断（支持 field metadata）
        strategy = StrategyFactory.get_factory().create_strategy(strategy_id)
        if hasattr(strategy, "config"):
            config = strategy.config
            if is_dataclass(config):
                # 使用 fields() 获取 field metadata
                config_fields = fields(config)
                config_dict = asdict(config)
                
                params = []
                
                for field_obj in config_fields:
                    field_name = field_obj.name
                    field_value = config_dict[field_name]
                    
                    # 跳过非优化参数
                    if isinstance(field_value, (list, dict)) or field_name.startswith('_'):
                        continue
                    
                    # 从 metadata 中提取参数信息
                    metadata = field_obj.metadata if hasattr(field_obj, 'metadata') else {}
                    
                    # 如果 metadata 中明确标记了 optimize=False，跳过
                    if metadata.get("optimize", True) is False:
                        continue
                    
                    # 从 metadata 中获取类型，否则根据默认值推断
                    param_type = metadata.get("type") or ('int' if isinstance(field_value, int) else 'float')
                    
                    # 从 metadata 中获取 min/max，如果没有则返回 None（让前端决定）
                    param_min = metadata.get("min")
                    param_max = metadata.get("max")
                    
                    # 如果 metadata 中没有 min/max，返回 None（让前端决定）
                    # 前端可以通过 CUSTOM_PARAM_CONFIG 覆盖，或使用默认范围生成器
                    
                    params.append({
                        "key": field_name,
                        "label": metadata.get("label", field_name),
                        "group": metadata.get("group", "其它"),
                        "type": param_type,
                        "min": param_min,
                        "max": param_max,
                        "step": metadata.get("step"),
                        "default": field_value,
                        "description": metadata.get("description", ""),
                        "optimize": metadata.get("optimize", True),
                    })
                
                return params
            elif isinstance(config, dict):
                # 兼容旧式字典配置（无 metadata）
                params = []
                for field_name, field_value in config.items():
                    if isinstance(field_value, (list, dict)) or field_name.startswith('_'):
                        continue
                    param_type = 'int' if isinstance(field_value, int) else 'float'
                    params.append({
                        "key": field_name,
                        "label": field_name,
                        "type": param_type,
                        "min": None,
                        "max": None,
                        "default": field_value,
                        "description": ""
                    })
                return params
            else:
                return []

        # 4. 实在啥都没有，就返回空
        return []

