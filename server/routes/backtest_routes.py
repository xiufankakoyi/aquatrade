"""
回测相关路由
"""
from flask import Blueprint, request, Response
from server.performance_utils import json_response
import pandas as pd
import io
import json

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


@backtest_bp.route('/analyze_report', methods=['POST'])
def analyze_report():
    """
    接收前端发来的回测结果，让 AI 进行分析
    
    请求体:
        {
            "strategy_id": "ai_gen_12345",
            "backtest_result": { ...完整的回测结果... }
        }
    
    返回:
        流式响应，包含进度更新和最终报告
    """
    try:
        from server.services.analysis_service import AnalysisService
        from server.services.strategy_service import StrategyService
        from config.logger import get_logger
        import json
        
        logger = get_logger(__name__)
        
        data = request.get_json() or {}
        strategy_id = data.get('strategy_id', '')
        backtest_result = data.get('backtest_result')
        
        if not backtest_result:
            return json_response(
                {"success": False, "error": "回测结果不能为空"}, 
                status_code=400
            )
        
        def generate_report_stream():
            """生成带有进度更新的流式响应"""
            # 发送初始进度
            yield f"progress:{json.dumps({'progress': 0, 'stage': '准备分析数据...'})}\n"
            
            # 1. 获取策略源代码 (为了让 AI 结合逻辑看数据)
            strategy_code = ""
            if strategy_id:
                try:
                    strategy_service = StrategyService()
                    yield f"progress:{json.dumps({'progress': 10, 'stage': '获取策略源代码...'})}\n"
                    strategy_code = strategy_service.get_strategy_code(strategy_id)
                    if not strategy_code:
                        logger.warning(f"无法获取策略 {strategy_id} 的源代码，将仅基于回测数据进行分析")
                except Exception as e:
                    logger.warning(f"获取策略源代码失败: {e}，将仅基于回测数据进行分析")
            
            yield f"progress:{json.dumps({'progress': 25, 'stage': '数据预处理...'})}\n"
            
            # 2. 生成分析报告
            analysis_service = AnalysisService()
            
            # 从回测结果中获取策略名称
            strategy_name = (
                backtest_result.get('strategyInfo', {}).get('name') or 
                strategy_id or 
                '未知策略'
            )
            
            logger.info(f"开始生成策略分析报告: {strategy_name} (ID: {strategy_id})")
            
            yield f"progress:{json.dumps({'progress': 50, 'stage': 'AI 深度分析中...'})}\n"
            
            # 开启真正的流式文本生成
            for chunk in analysis_service.generate_review_stream(
                strategy_name=strategy_name,
                backtest_result=backtest_result,
                strategy_code=strategy_code
            ):
                yield f"stream:{json.dumps({'content': chunk})}\n"
            
            yield f"progress:{json.dumps({'progress': 100, 'stage': '分析完成'})}\n"
        
        # 返回流式响应
        return Response(
            generate_report_stream(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        from config.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"生成分析报告失败: {e}", exc_info=True)
        return json_response(
            {"success": False, "error": f"生成分析报告失败: {str(e)}"}, 
            status_code=500
        )