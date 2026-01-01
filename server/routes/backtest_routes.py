"""
回测相关路由
"""
from flask import Blueprint, request
from server.performance_utils import json_response

backtest_bp = Blueprint('backtest', __name__, url_prefix='/api')


@backtest_bp.route('/run_backtest', methods=['POST'])
def run_backtest():
    """非流式备选接口"""
    # 延迟导入避免循环依赖
    from server.app import get_api
    
    try:
        data = request.get_json() or {}
        strategy_name = data.get('strategy_name')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        profile_id = data.get('profile_id')
        override_params = data.get('override_params') or {}

        # 如果提供了 profile_id，则从 DuckDB 中加载对应的参数预设
        if profile_id is not None:
            from core.profiles.profile_repository import get_profile as load_profile

            profile = load_profile(int(profile_id))
            if profile is None:
                return json_response({"success": False, "error": f"Profile {profile_id} 不存在"}, status_code=400)
            # 合并 profile 参数和本次请求的覆盖参数
            params_from_profile = profile.get("params") or {}
            if not isinstance(params_from_profile, dict):
                params_from_profile = {}
            if not isinstance(override_params, dict):
                override_params = {}
            effective_params = {**params_from_profile, **override_params}
        else:
            # 不使用 Profile，直接使用请求体中的参数
            effective_params = data.get('params') or {}

        result = get_api().run_backtest_and_get_data(
            strategy_name,
            start_date,
            end_date,
            params=effective_params,
        )
        # 使用 orjson 加速响应
        return json_response({"success": True, "data": result})
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"回测失败: {e}", exc_info=True)
        return json_response({"success": False, "error": str(e)}, status_code=500)
