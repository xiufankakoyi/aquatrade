"""
策略配置管理 API

提供策略配置的 CRUD 接口和热重载功能
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from core.strategies.hot_reload import ConfigManager, StrategyLoader, get_config_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/strategies", tags=["策略配置"])


@router.get("/{strategy_id}/config")
async def get_strategy_config(strategy_id: str):
    """
    获取策略配置
    
    参数：
        strategy_id: 策略ID
    
    返回：
        配置参数字典
    """
    try:
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
            "strategy_id": strategy_id
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
