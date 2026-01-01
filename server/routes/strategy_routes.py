"""
策略相关路由
"""
from flask import Blueprint, jsonify, request
from urllib.parse import unquote
from server.performance_utils import json_response

strategy_bp = Blueprint('strategy', __name__, url_prefix='/api')


@strategy_bp.route('/strategies', methods=['GET'])
def get_strategies():
    """获取策略列表"""
    # 延迟导入避免循环依赖
    from server.app import _normalize_strategy_id
    
    try:
        from core.strategies.strategy_factory import get_factory
        factory = get_factory()
        strategies = factory.list_strategies()

        result = []
        for i, strategy in enumerate(strategies):
            raw_name = strategy.get('name', '')
            safe_id = _normalize_strategy_id(raw_name)
            strategy_id = strategy.get('id') or raw_name or safe_id or f"strategy_{i}"

            # 检查重复，如果已存在则添加索引后缀
            if len([s for s in result if s['id'] == strategy_id]) > 0:
                strategy_id = f"{strategy_id}_{i}"

            result.append({
                "id": strategy_id,
                "name": raw_name or strategy_id,
                "safeId": safe_id
            })

        return json_response({"success": True, "data": result})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取策略列表失败: {e}", exc_info=True)
        return json_response({"success": False, "data": [], "error": str(e)}, status_code=500)


@strategy_bp.route('/test_strategies', methods=['GET'])
def test_get_strategies():
    """测试用策略列表端点"""
    try:
        test_strategies = [
            {"id": "test_strategy_1", "name": "测试策略1", "description": "这是第一个测试策略"},
            {"id": "test_strategy_2", "name": "测试策略2", "description": "这是第二个测试策略"}
        ]
        return json_response({"success": True, "data": test_strategies})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"测试端点失败: {e}")
        return json_response({"success": False, "error": str(e)}, status_code=500)


@strategy_bp.route('/strategies/<strategy_id>/params', methods=['GET'])
def get_strategy_params(strategy_id: str):
    """获取指定策略的可优化参数列表"""
    # 延迟导入避免循环依赖
    from server.app import get_api, _normalize_strategy_id
    
    try:
        resolved_id = unquote(strategy_id)
        try:
            params = get_api().get_strategy_params(resolved_id)
        except Exception:
            # 尝试使用 safeId 匹配原始策略名
            from core.strategies.strategy_factory import get_factory
            factory = get_factory()
            for item in factory.list_strategies():
                raw_name = item.get('name', '')
                if _normalize_strategy_id(raw_name) == resolved_id:
                    resolved_id = raw_name
                    break
            params = get_api().get_strategy_params(resolved_id)
        return json_response(params)
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取策略参数失败: {e}", exc_info=True)
        return json_response({"error": str(e)}, status_code=500)


@strategy_bp.route('/strategies/<strategy_name>/profiles', methods=['GET'])
def get_strategy_profiles(strategy_name: str):
    """获取策略的参数预设列表"""
    try:
        from core.profiles.profile_repository import list_profiles as list_strategy_profiles
        profiles = list_strategy_profiles(strategy_name)
        return json_response({"success": True, "data": profiles})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取策略预设失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@strategy_bp.route('/strategies/<strategy_name>/profiles', methods=['POST'])
def create_strategy_profile(strategy_name: str):
    """创建策略的参数预设"""
    try:
        data = request.get_json() or {}
        profile_name = data.get('name', '')
        params = data.get('params', {})
        
        if not profile_name:
            return json_response({"success": False, "error": "预设名称不能为空"}, status_code=400)
        
        from core.profiles.profile_repository import create_profile as create_strategy_profile
        profile_id = create_strategy_profile(strategy_name, profile_name, params)
        
        return json_response({"success": True, "data": {"id": profile_id}})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"创建策略预设失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)


@strategy_bp.route('/strategy-profiles/<int:profile_id>', methods=['GET'])
def get_profile(profile_id: int):
    """获取指定的参数预设"""
    try:
        from core.profiles.profile_repository import get_profile as get_strategy_profile
        profile = get_strategy_profile(profile_id)
        if profile is None:
            return json_response({"success": False, "error": "预设不存在"}, status_code=404)
        return json_response({"success": True, "data": profile})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取预设失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)

