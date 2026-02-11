"""
路由模块
统一导出所有路由蓝图
"""
from flask import Blueprint

# 延迟导入，避免循环依赖
def register_routes(app):
    """注册所有路由到 Flask 应用"""
    from server.routes.strategy_routes import strategy_bp
    from server.routes.backtest_routes import backtest_bp
    from server.routes.data_routes import data_bp
    from server.routes.scatter_routes import scatter_bp
    from server.routes.sentiment_routes import sentiment_bp
    from server.routes.optimization_routes import optimization_bp
    from server.routes.system_routes import system_bp
    from server.routes.dragon_eye_routes import dragon_bp
    
    app.register_blueprint(strategy_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(scatter_bp)
    app.register_blueprint(sentiment_bp)
    app.register_blueprint(optimization_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(dragon_bp)

