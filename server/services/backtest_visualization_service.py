"""
回测可视化主服务
作为服务门面，组合所有子服务，提供统一接口
"""
from typing import Dict, List, Any, Optional, Generator
from threading import Event
from server.services.data_initialization_service import DataInitializationService
from server.services.stock_data_service import StockDataService
from server.services.strategy_service import StrategyService
from server.services.backtest_service import BacktestService
from server.services.metrics_service import MetricsService
from server.services.guba_service import GubaService


class BacktestVisualizationService:
    """回测可视化主服务类（服务门面）"""
    
    def __init__(self, db_path: Optional[str] = None):
        # 初始化各个子服务
        self.init_service = DataInitializationService(db_path)
        self.stock_data_service = StockDataService(self.init_service)
        self.strategy_service = StrategyService()
        self.metrics_service = MetricsService(self.init_service, self.stock_data_service)
        self.backtest_service = BacktestService(self.init_service, self.metrics_service, self.stock_data_service)
        self.guba_service = GubaService(self.init_service, self.stock_data_service)
    
    # 数据初始化相关方法
    def _ensure_initialized(self) -> None:
        """确保数据库已初始化（兼容层方法）"""
        self.init_service.ensure_initialized()
    
    @property
    def data_query(self):
        """获取数据查询对象（兼容层属性）"""
        return self.init_service.data_query
    
    @property
    def backtest_engine(self):
        """获取回测引擎（兼容层属性）"""
        return self.init_service.backtest_engine
    
    @property
    def stock_info_map(self) -> Dict[str, str]:
        """获取股票信息映射（兼容层属性）"""
        return self.init_service.stock_info_map
    
    @property
    def initial_capital(self) -> float:
        """获取初始资金（兼容层属性）"""
        return self.init_service.initial_capital
    
    @property
    def _initialized(self) -> bool:
        """获取初始化状态（兼容层属性）"""
        return self.init_service._initialized
    
    # 策略相关方法
    def get_strategy_list(self) -> List[Dict]:
        """获取策略列表"""
        return self.strategy_service.get_strategy_list()
    
    def get_strategy_logic(self, strategy_id: str) -> Dict[str, Any]:
        """获取策略的逻辑描述"""
        return self.strategy_service.get_strategy_logic(strategy_id)
    
    def get_strategy_params(self, strategy_id: str) -> list[dict]:
        """返回给前端用的参数列表"""
        return self.strategy_service.get_strategy_params(strategy_id)
    
    # 股票数据相关方法
    def get_symbol_kline(self, symbol_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取K线数据（强制全局前复权）"""
        return self.stock_data_service.get_symbol_kline(symbol_code, start_date, end_date)
    
    def get_latest_prices(self, symbol_codes: List[str], target_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """获取最新价格（强制全局前复权）"""
        return self.stock_data_service.get_latest_prices(symbol_codes, target_date)
    
    # 回测相关方法
    def run_backtest_and_get_data(self, strategy_name: str, start_date: str, end_date: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """运行回测并获取数据（真实数据，作为备用）"""
        return self.backtest_service.run_backtest_and_get_data(strategy_name, start_date, end_date, params)
    
    def stream_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        benchmark_code: Optional[str] = None,
        stop_event: Optional[Event] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """流式回测"""
        return self.backtest_service.stream_backtest(
            strategy_name, start_date, end_date, benchmark_code, stop_event, params
        )
    
    # 股吧相关方法
    def get_scatter_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """获取情感-热度散点图数据"""
        return self.guba_service.get_scatter_data(symbol)
    
    # 内部方法（用于兼容层）
    def _get_global_latest_factor(self, symbol_code: str) -> float:
        """获取全局最新复权因子（兼容层方法）"""
        return self.init_service.get_global_latest_factor(symbol_code)
    
    def _get_stock_info_with_market_cap(self, needed_symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """获取股票基础信息（名称、市值）（兼容层方法）"""
        return self.stock_data_service.get_stock_info_with_market_cap(needed_symbols)
    
    def _load_guba_posts_from_parquet(self, symbol: Optional[str] = None, sample_size: int = 50) -> Any:
        """从 Parquet 文件加载股吧数据（兼容层方法）"""
        return self.guba_service.load_guba_posts_from_parquet(symbol, sample_size)
    
    def _normalize_symbol_code(self, symbol_code: Optional[str]) -> str:
        """规范化股票代码（兼容层方法）"""
        from server.utils.symbol_utils import normalize_symbol_code
        return normalize_symbol_code(symbol_code)
    
    def _normalize_symbol_key(self, raw_symbol: str, stock_code: str) -> str:
        """规范化股票代码为标准格式（兼容层方法）"""
        from server.utils.symbol_utils import normalize_symbol_key
        return normalize_symbol_key(raw_symbol, stock_code)
    
    def _calculate_qfq_dataframe(self, df: Any) -> Any:
        """计算前复权DataFrame（兼容层方法）"""
        from server.utils.qfq_utils import calculate_qfq_dataframe
        return calculate_qfq_dataframe(df)
    
    def _get_benchmark_data_from_db(self, benchmark_code: str, start_date: str, end_date: str) -> Any:
        """获取基准数据（兼容层方法）"""
        return self.stock_data_service.get_benchmark_data_from_db(benchmark_code, start_date, end_date)
    
    def _calculate_metrics_from_df(self, results_df: Any, trades_log: List[Dict]) -> Dict:
        """计算指标（兼容层方法）"""
        return self.metrics_service.calculate_metrics_from_df(results_df, trades_log)
    
    def _extract_equity_curve_from_df(self, results_df: Any) -> Dict:
        """提取权益曲线（兼容层方法）"""
        return self.metrics_service.extract_equity_curve_from_df(results_df, self.stock_data_service)
    
    def _calculate_risk_from_df(self, results_df: Any) -> Dict:
        """计算风险指标（兼容层方法）"""
        return self.metrics_service.calculate_risk_from_df(results_df)
    
    def _convert_backtest_results(self, results_df: Any, trades_log: List[Dict], 
                                 strategy_name: str, start_date: str, end_date: str) -> Dict:
        """转换回测结果（兼容层方法）"""
        return self.backtest_service.convert_backtest_results(results_df, trades_log, strategy_name, start_date, end_date)

