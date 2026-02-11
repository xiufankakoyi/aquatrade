"""
策略配置管理 API - Flask 版本

提供策略配置的 CRUD 接口和热重载功能
"""

from flask import Blueprint, request, jsonify
import logging

from core.strategies.hot_reload import ConfigManager, StrategyLoader, get_config_manager

logger = logging.getLogger(__name__)

# 创建 Blueprint
config_bp = Blueprint('strategy_config', __name__, url_prefix='/api/strategies')


@config_bp.route('/<strategy_id>/config', methods=['GET'])
def get_strategy_config(strategy_id):
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
                return jsonify({
                    "success": False,
                    "error": f"策略配置未找到且无法生成: {e}"
                }), 404
        
        return jsonify({
            "success": True,
            "data": config,
            "strategy_id": strategy_id
        })
        
    except Exception as e:
        logger.error(f"获取配置失败: {strategy_id}, 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@config_bp.route('/<strategy_id>/config', methods=['PUT'])
def update_strategy_config(strategy_id):
    """
    更新策略配置（自动触发热重载）
    
    参数：
        strategy_id: 策略ID
        config: 新配置参数（JSON body）
    
    返回：
        更新结果
    """
    try:
        config = request.get_json()
        if not config:
            return jsonify({"success": False, "error": "配置数据为空"}), 400
        
        config_mgr = get_config_manager()
        
        # 1. 保存配置
        if not config_mgr.save_config(strategy_id, config):
            return jsonify({"success": False, "error": "配置保存失败"}), 500
        
        # 2. 触发热重载
        try:
            reloaded_strategy = StrategyLoader.reload_strategy(strategy_id, config=config)
            logger.info(f"✅ 策略配置更新并重载成功: {strategy_id}")
            
            return jsonify({
                "success": True,
                "message": f"配置已更新，策略 {strategy_id} 已重载",
                "strategy_name": getattr(reloaded_strategy, 'strategy_name', strategy_id)
            })
        except Exception as reload_error:
            logger.warning(f"配置已保存但重载失败: {reload_error}")
            return jsonify({
                "success": True,
                "message": f"配置已保存，但重载失败: {reload_error}",
                "warning": "请手动重启服务器或触发重载"
            }), 200
        
    except Exception as e:
        logger.error(f"更新配置失败: {strategy_id}, 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@config_bp.route('/<strategy_id>/reload', methods=['POST'])
def reload_strategy_manual(strategy_id):
    """
    手动触发策略重载
    
    参数：
        strategy_id: 策略ID
    
    返回：
        重载结果
    """
    try:
        reloaded_strategy = StrategyLoader.reload_strategy(strategy_id)
        config_mgr = get_config_manager()
        
        return jsonify({
            "success": True,
            "message": f"策略 {strategy_id} 重载成功",
            "strategy_name": getattr(reloaded_strategy, 'strategy_name', strategy_id),
            "config": config_mgr.load_config(strategy_id)
        })
        
    except Exception as e:
        logger.error(f"手动重载失败: {strategy_id}, 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@config_bp.route('/configs/list', methods=['GET'])
def list_all_configs():
    """
    列出所有可用的配置文件
    
    返回：
        配置文件列表
    """
    try:
        config_mgr = get_config_manager()
        config_list = config_mgr.list_configs()
        
        return jsonify({
            "success": True,
            "data": config_list,
            "count": len(config_list)
        })
        
    except Exception as e:
        logger.error(f"列出配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@config_bp.route('/<strategy_id>/config/reset', methods=['POST'])
def reset_strategy_config(strategy_id):
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
            return jsonify({"success": False, "error": "无法获取默认配置"}), 404
        
        # 保存默认配置
        if config_mgr.save_config(strategy_id, default_config):
            # 重载策略
            StrategyLoader.reload_strategy(strategy_id, config=default_config)
            
            return jsonify({
                "success": True,
                "message": f"策略 {strategy_id} 已重置为默认配置",
                "config": default_config
            })
        else:
            return jsonify({"success": False, "error": "配置保存失败"}), 500
        
    except Exception as e:
        logger.error(f"重置配置失败: {strategy_id}, 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# 导出 blueprint
__all__ = ['config_bp']
