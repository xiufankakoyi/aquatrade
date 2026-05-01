"""
策略配置管理 API (增强版)

提供策略配置的 CRUD 接口和热重载功能
支持新的配置化策略系统 (YAML/JSON)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
import logging

from core.strategies.strategy_factory import get_factory
from core.strategies.configurable import (
    StrategyConfigLoader,
    StrategyConfig,
    ConfigurableStrategy,
    list_indicators,
    get_indicator_metadata,
)
from core.strategies.hot_reload import ConfigManager, StrategyLoader, get_config_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/strategies", tags=["策略配置"])


# ==================== 配置化策略 API ====================

@router.get("/configurable/list")
async def list_configurable_strategies():
    """
    列出所有配置化策略
    
    返回：
        配置化策略列表
    """
    try:
        factory = get_factory()
        strategies = factory.list_config_strategies()
        
        return {
            "success": True,
            "data": strategies,
            "count": len(strategies)
        }
        
    except Exception as e:
        logger.error(f"列出配置化策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configurable/{strategy_id}")
async def get_configurable_strategy(strategy_id: str):
    """
    获取配置化策略详情
    
    参数：
        strategy_id: 策略ID
    
    返回：
        策略配置详情
    """
    try:
        factory = get_factory()
        config = factory.get_config_strategy(strategy_id)
        
        if config is None:
            raise HTTPException(status_code=404, detail=f"策略未找到: {strategy_id}")
        
        return {
            "success": True,
            "data": config.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略详情失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configurable")
async def create_configurable_strategy(config_data: Dict[str, Any]):
    """
    创建新的配置化策略
    
    参数：
        config_data: 策略配置数据
    
    返回：
        创建结果
    """
    try:
        loader = StrategyConfigLoader()
        config = loader.load_from_dict(config_data)
        
        # 保存配置
        config_path = f"{config.strategy_id}.yaml"
        loader.save(config, config_path)
        
        # 刷新工厂注册表
        factory = get_factory()
        factory._discover_config_strategies()
        
        return {
            "success": True,
            "message": f"策略 {config.strategy_id} 创建成功",
            "data": config.to_dict()
        }
        
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configurable/{strategy_id}")
async def update_configurable_strategy(strategy_id: str, config_data: Dict[str, Any]):
    """
    更新配置化策略
    
    参数：
        strategy_id: 策略ID
        config_data: 新的策略配置数据
    
    返回：
        更新结果
    """
    try:
        factory = get_factory()
        existing_config = factory.get_config_strategy(strategy_id)
        
        if existing_config is None:
            raise HTTPException(status_code=404, detail=f"策略未找到: {strategy_id}")
        
        # 确保ID一致
        config_data['strategy_id'] = strategy_id
        
        loader = StrategyConfigLoader()
        config = loader.load_from_dict(config_data)
        
        # 保存配置
        config_path = f"{strategy_id}.yaml"
        loader.save(config, config_path)
        
        # 刷新工厂注册表
        factory._discover_config_strategies()
        
        return {
            "success": True,
            "message": f"策略 {strategy_id} 更新成功",
            "data": config.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新策略失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configurable/{strategy_id}")
async def delete_configurable_strategy(strategy_id: str):
    """
    删除配置化策略
    
    参数：
        strategy_id: 策略ID
    
    返回：
        删除结果
    """
    try:
        factory = get_factory()
        config = factory.get_config_strategy(strategy_id)
        
        if config is None:
            raise HTTPException(status_code=404, detail=f"策略未找到: {strategy_id}")
        
        # 删除配置文件
        from pathlib import Path
        configs_dir = Path(__file__).parent.parent.parent / "core" / "strategies" / "configs"
        
        for ext in ['.yaml', '.yml', '.json']:
            config_file = configs_dir / f"{strategy_id}{ext}"
            if config_file.exists():
                config_file.unlink()
                break
        
        # 刷新工厂注册表
        factory._discover_config_strategies()
        
        return {
            "success": True,
            "message": f"策略 {strategy_id} 已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除策略失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configurable/{strategy_id}/validate")
async def validate_configurable_strategy(strategy_id: str, parameters: Optional[Dict[str, Any]] = None):
    """
    验证策略配置和参数
    
    参数：
        strategy_id: 策略ID
        parameters: 要验证的参数（可选，不传则验证默认参数）
    
    返回：
        验证结果
    """
    try:
        factory = get_factory()
        config = factory.get_config_strategy(strategy_id)
        
        if config is None:
            raise HTTPException(status_code=404, detail=f"策略未找到: {strategy_id}")
        
        # 验证参数
        params_to_validate = parameters or config.get_default_params()
        errors = config.validate_params(params_to_validate)
        
        if errors:
            return {
                "success": False,
                "valid": False,
                "errors": errors
            }
        
        return {
            "success": True,
            "valid": True,
            "message": "参数验证通过"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证策略失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 指标 API ====================

@router.get("/indicators/list")
async def list_available_indicators():
    """
    列出所有可用的指标
    
    返回：
        指标列表及其元数据
    """
    try:
        indicators = list_indicators()
        result = []
        
        for name in indicators:
            try:
                metadata = get_indicator_metadata(name)
                result.append({
                    "name": name,
                    "description": metadata.get("description", ""),
                    "params_schema": metadata.get("params_schema", {}),
                })
            except Exception:
                result.append({
                    "name": name,
                    "description": "",
                    "params_schema": {},
                })
        
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
        
    except Exception as e:
        logger.error(f"列出指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators/{indicator_name}")
async def get_indicator_detail(indicator_name: str):
    """
    获取指标详情
    
    参数：
        indicator_name: 指标名称
    
    返回：
        指标详细信息
    """
    try:
        metadata = get_indicator_metadata(indicator_name)
        
        return {
            "success": True,
            "data": {
                "name": indicator_name,
                "description": metadata.get("description", ""),
                "params_schema": metadata.get("params_schema", {}),
                "signature": metadata.get("signature", ""),
            }
        }
        
    except Exception as e:
        logger.error(f"获取指标详情失败: {indicator_name}, 错误: {e}")
        raise HTTPException(status_code=404, detail=f"指标未找到: {indicator_name}")


# ==================== 原有 API（向后兼容）====================

@router.get("/{strategy_id}/config")
async def get_strategy_config(strategy_id: str):
    """
    获取策略配置（向后兼容）
    
    参数：
        strategy_id: 策略ID
    
    返回：
        配置参数字典
    """
    try:
        # 首先尝试获取配置化策略
        factory = get_factory()
        config = factory.get_config_strategy(strategy_id)
        
        if config:
            return {
                "success": True,
                "data": config.to_dict(),
                "strategy_id": strategy_id,
                "type": "configurable"
            }
        
        # 否则使用原有的配置管理器
        config_mgr = get_config_manager()
        config = config_mgr.load_config(strategy_id)
        
        if config is None:
            # 如果配置文件不存在，尝试从策略类提取默认配置
            try:
                strategy = StrategyLoader.load_strategy(strategy_id)
                config = config_mgr.get_default_config(strategy.__class__)
                
                # 保存默认配置
                if config:
                    config_mgr.save_config(strategy_id, config)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"策略配置未找到且无法生成: {e}")
        
        return {
            "success": True,
            "data": config,
            "strategy_id": strategy_id,
            "type": "legacy"
        }
        
    except Exception as e:
        logger.error(f"获取配置失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{strategy_id}/config")
async def update_strategy_config(strategy_id: str, config: Dict[str, Any]):
    """
    更新策略配置（自动触发热重载）
    
    参数：
        strategy_id: 策略ID
        config: 新配置参数
    
    返回：
        更新结果
    """
    try:
        config_mgr = get_config_manager()
        
        # 1. 验证配置（可选）
        # 可以添加配置验证逻辑
        
        # 2. 保存配置
        if not config_mgr.save_config(strategy_id, config):
            raise HTTPException(status_code=500, detail="配置保存失败")
        
        # 3. 触发热重载
        try:
            reloaded_strategy = StrategyLoader.reload_strategy(strategy_id, config=config)
            logger.info(f"✅ 策略配置更新并重载成功: {strategy_id}")
            
            return {
                "success": True,
                "message": f"配置已更新，策略 {strategy_id} 已重载",
                "strategy_name": getattr(reloaded_strategy, 'strategy_name', strategy_id)
            }
        except Exception as reload_error:
            logger.warning(f"配置已保存但重载失败: {reload_error}")
            return {
                "success": True,
                "message": f"配置已保存，但重载失败: {reload_error}",
                "warning": "请手动重启服务器或触发重载"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/reload")
async def reload_strategy_manual(strategy_id: str):
    """
    手动触发策略重载
    
    参数：
        strategy_id: 策略ID
    
    返回：
        重载结果
    """
    try:
        reloaded_strategy = StrategyLoader.reload_strategy(strategy_id)
        
        return {
            "success": True,
            "message": f"策略 {strategy_id} 重载成功",
            "strategy_name": getattr(reloaded_strategy, 'strategy_name', strategy_id),
            "config": config_mgr.load_config(strategy_id) if (config_mgr := get_config_manager()) else None
        }
        
    except Exception as e:
        logger.error(f"手动重载失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs/list")
async def list_all_configs():
    """
    列出所有可用的配置文件
    
    返回：
        配置文件列表
    """
    try:
        config_mgr = get_config_manager()
        config_list = config_mgr.list_configs()
        
        return {
            "success": True,
            "data": config_list,
            "count": len(config_list)
        }
        
    except Exception as e:
        logger.error(f"列出配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/config/reset")
async def reset_strategy_config(strategy_id: str):
    """
    重置策略配置为默认值
    
    参数：
        strategy_id: 策略ID
    
    返回：
        重置结果
    """
    try:
        config_mgr = get_config_manager()
        
        # 加载策略获取默认配置
        strategy = StrategyLoader.load_strategy(strategy_id)
        default_config = config_mgr.get_default_config(strategy.__class__)
        
        if not default_config:
            raise HTTPException(status_code=404, detail="无法获取默认配置")
        
        # 保存默认配置
        if config_mgr.save_config(strategy_id, default_config):
            # 重载策略
            StrategyLoader.reload_strategy(strategy_id, config=default_config)
            
            return {
                "success": True,
                "message": f"策略 {strategy_id} 已重置为默认配置",
                "config": default_config
            }
        else:
            raise HTTPException(status_code=500, detail="配置保存失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置配置失败: {strategy_id}, 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
