"""
路由模块
统一导出所有路由蓝图
"""
from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# 延迟导入，避免循环依赖
def register_routes(app):
    """注册所有路由到 Flask 应用"""
    
    # 定义所有路由模块，每个都包含错误处理
    route_modules = [
        ('server.routes.strategy_routes', 'strategy_bp'),
        ('server.routes.backtest_routes', 'backtest_bp'),
        ('server.routes.data_routes', 'data_bp'),
        ('server.routes.scatter_routes', 'scatter_bp'),
        ('server.routes.sentiment_routes', 'sentiment_bp'),
        ('server.routes.optimization_routes', 'optimization_bp'),
        ('server.routes.system_routes', 'system_bp'),
        ('server.routes.dragon_eye_routes', 'dragon_bp'),
        ('server.routes.portfolio_routes', 'portfolio_bp'),
        ('server.routes.game_routes', 'game_bp'),
        ('server.routes.screener_routes', 'screener_bp'),
        ('server.routes.export_routes', 'export_bp'),
        ('server.routes.similarity_routes', 'similarity_bp'),
        ('server.routes.event_routes', 'event_bp'),
        ('server.routes.pattern_routes', 'pattern_bp'),
        ('server.concept_lab.concept_api', 'concept_bp'),
        ('server.routes.news_routes', 'news_bp'),
        ('server.industry_chain.api', 'industry_chain_bp'),
    ]
    
    for module_name, bp_name in route_modules:
        try:
            module = __import__(module_name, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint)
            logger.info(f"路由注册成功: {module_name}")
        except Exception as e:
            logger.warning(f"路由注册失败: {module_name} - {e}")

