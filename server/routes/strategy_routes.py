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
        return json_response([])


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


@strategy_bp.route('/strategies/generate', methods=['POST'])
def generate_strategy():
    """使用 AI 生成策略代码"""
    try:
        data = request.get_json() or {}
        user_description = data.get('description', '').strip()
        strategy_name = data.get('name', 'AI策略').strip()

        if not user_description:
            return json_response(
                {"success": False, "error": "策略描述不能为空"},
                status_code=400
            )

        if not strategy_name:
            strategy_name = "AI策略"

        from server.services.strategy_generator import StrategyGenerator
        generator = StrategyGenerator()

        filename = generator.create_strategy(
            user_description=user_description,
            strategy_name=strategy_name
        )

        return json_response({
            "success": True,
            "data": {
                "filename": filename,
                "message": f"策略已成功生成并保存为 {filename}"
            }
        })

    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"生成策略失败: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": f"生成策略失败: {str(e)}"},
            status_code=500
        )


@strategy_bp.route('/strategies/reload', methods=['POST'])
def reload_strategies():
    """
    手动触发策略热重载

    请求体:
        - strategy_id: 指定策略ID（可选）
        - file_path: 指定文件路径（可选）
        - refresh_all: 是否刷新所有策略（默认 False）
    """
    try:
        data = request.get_json() or {}
        strategy_id = data.get('strategy_id')
        file_path = data.get('file_path')
        refresh_all = data.get('refresh_all', False)

        from core.strategies.hot_reload import StrategyLoader, get_watcher

        watcher = get_watcher()

        if strategy_id:
            StrategyLoader.reload_strategy(strategy_id)
            return json_response({
                "success": True,
                "data": {
                    "action": "reload_strategy",
                    "strategy_id": strategy_id,
                    "message": f"策略 {strategy_id} 已重载"
                }
            })
        elif file_path:
            result = StrategyLoader.reload_by_path(file_path)
            if result:
                return json_response({
                    "success": True,
                    "data": {
                        "action": "reload_by_path",
                        "file_path": file_path,
                        "strategy_id": result,
                        "message": f"文件 {file_path} 已重载为策略 {result}"
                    }
                })
            else:
                return json_response({
                    "success": False,
                    "error": f"无法识别文件: {file_path}"
                }, status_code=400)
        elif refresh_all:
            strategies = StrategyLoader.discover_strategies(force_refresh=True)
            return json_response({
                "success": True,
                "data": {
                    "action": "refresh_all",
                    "strategies": list(strategies.keys()),
                    "count": len(strategies),
                    "message": f"已刷新 {len(strategies)} 个策略"
                }
            })
        else:
            success = watcher.trigger_reload()
            if success:
                return json_response({
                    "success": True,
                    "data": {
                        "action": "trigger_reload",
                        "message": "策略发现缓存已刷新"
                    }
                })
            else:
                return json_response({
                    "success": False,
                    "error": "重载失败"
                }, status_code=500)

    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"策略重载失败: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": f"策略重载失败: {str(e)}"},
            status_code=500
        )


@strategy_bp.route('/strategies/discovered', methods=['GET'])
def get_discovered_strategies():
    """获取已发现的策略列表（来自热重载模块）"""
    try:
        from core.strategies.hot_reload import StrategyLoader

        strategies = StrategyLoader.discover_strategies()

        result = [
            {"id": sid, "module_path": mpath}
            for sid, mpath in strategies.items()
        ]

        return json_response({
            "success": True,
            "data": {
                "strategies": result,
                "count": len(result)
            }
        })

    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"获取已发现策略失败: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": str(e)},
            status_code=500
        )


@strategy_bp.route('/strategies/save', methods=['POST'])
def save_strategy():
    """
    保存策略代码到文件

    请求体:
        - name: 策略名称（必需）
        - description: 策略描述（可选）
        - code: 策略代码（必需）
        - temp: 是否临时保存（可选，默认 False）
    """
    try:
        data = request.get_json() or {}
        strategy_name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        code = data.get('code', '').strip()
        is_temp = data.get('temp', False)

        if not strategy_name:
            return json_response(
                {"success": False, "error": "策略名称不能为空"},
                status_code=400
            )

        if not code:
            return json_response(
                {"success": False, "error": "策略代码不能为空"},
                status_code=400
            )

        # 生成文件名（使用策略名称的拼音或英文）
        import re
        import os

        # 将策略名称转换为有效的文件名
        # 移除特殊字符，替换空格为下划线
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', strategy_name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')

        # 如果名称是中文，使用时间戳作为后缀
        if re.search(r'[\u4e00-\u9fff]', safe_name):
            import time
            safe_name = f"user_strategy_{int(time.time())}"

        filename = f"{safe_name}.py"

        # 如果是临时保存，使用临时目录
        if is_temp:
            import tempfile
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
        else:
            # 保存到用户策略目录
            user_strategies_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'core', 'strategies', 'user'
            )

            # 确保目录存在
            os.makedirs(user_strategies_dir, exist_ok=True)
            file_path = os.path.join(user_strategies_dir, filename)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            # 添加文件头注释
            if description:
                f.write(f'"""\n{description}\n"""\n\n')
            f.write(code)

        # 如果不是临时保存，触发策略重载
        if not is_temp:
            try:
                from core.strategies.hot_reload import StrategyLoader
                StrategyLoader.reload_by_path(file_path)
            except Exception as reload_error:
                from config.logger import get_logger
                logger = get_logger(__name__)
                logger.warning(f"策略保存后重载失败: {reload_error}")

        return json_response({
            "success": True,
            "data": {
                "filename": filename,
                "filepath": file_path,
                "message": f"策略已成功保存为 {filename}"
            }
        })

    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"保存策略失败: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": f"保存策略失败: {str(e)}"},
            status_code=500
        )


# ============================================================
# 策略信号质量评估接口
# ============================================================
@strategy_bp.route('/strategies/<strategy_id>/quality', methods=['POST'])
def evaluate_strategy_quality(strategy_id: str):
    """
    综合评估策略信号质量

    Request Body (JSON):
        - start_date: 开始日期 (YYYY-MM-DD, 必需)
        - end_date: 结束日期 (YYYY-MM-DD, 必需)
        - params: 策略参数字典（可选）
        - param_grid: 参数稳健性测试网格（可选），形如 {"fast_window": [3, 5, 7]}
        - n_windows: 长期有效性窗口数（默认 4）
        - n_permutations: 过拟合检测扰动次数（默认 3）

    Returns:
        包含 total_score / grade / dimensions 等字段的综合质量报告
    """
    from config.logger import get_logger
    logger = get_logger(__name__)

    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    if not start_date or not end_date:
        return json_response(
            {"success": False, "error": "start_date 和 end_date 必填"},
            status_code=400,
        )

    user_params = data.get('params') or {}
    param_grid = data.get('param_grid') or {}
    n_windows = int(data.get('n_windows') or 4)
    n_permutations = int(data.get('n_permutations') or 3)

    try:
        from core.strategies.strategy_factory import get_factory
        from core.strategies.signal_quality import SignalQualityEvaluator
        from core.backtest.unified_engine import UnifiedBacktestEngine

        factory = get_factory()
        strategy_cls = (
            factory.get_strategy_by_id(strategy_id)
            or factory.get_strategy_by_name(strategy_id)
        )
        if strategy_cls is None:
            return json_response(
                {"success": False, "error": f"未找到策略: {strategy_id}"},
                status_code=404,
            )

        # 构造策略工厂
        def strategy_factory(**extra):
            merged = {**user_params, **extra}
            return factory.create_strategy(strategy_id, True, **merged)

        # 构造回测引擎：尝试用项目内的 data_query，缺失则容错为 None（依赖 SignalQualityEvaluator 的失败降级）
        data_query = None
        try:
            from data_svc.database.optimized_data_query import OptimizedStockDataQuery
            data_query = OptimizedStockDataQuery(warmup=False)
        except Exception as inner_e:
            logger.warning(f"无法初始化策略质量评估 data_query: {inner_e}")

        engine = UnifiedBacktestEngine(data_query=data_query) if data_query is not None else None

        evaluator = SignalQualityEvaluator(engine=engine) if engine is not None else None
        if evaluator is None:
            return json_response(
                {"success": False, "error": "策略质量评估依赖回测引擎，但 data_query 不可用"},
                status_code=500,
            )

        report = evaluator.evaluate_all(
            strategy_factory=strategy_factory,
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            n_windows=n_windows,
            n_permutations=n_permutations,
        )
        return json_response({"success": True, "data": report.to_dict()})
    except Exception as e:
        logger.error(f"evaluate_strategy_quality failed: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": f"评估失败: {str(e)}"},
            status_code=500,
        )
