"""
数据初始化服务
负责数据库初始化、股票信息加载、复权因子管理
"""
from typing import Dict, Optional
import pandas as pd
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from config.config import Config
from config.logger import get_logger


class DataInitializationService:
    """数据初始化服务类"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        self.data_query: Optional[OptimizedStockDataQuery] = None
        self.backtest_engine: Optional[UnifiedBacktestEngine] = None
        self.stock_info_map: Dict[str, str] = {}
        self._initialized = False
        self.initial_capital = Config.INITIAL_CAPITAL
    
    def ensure_initialized(self) -> None:
        """确保数据库已初始化"""
        if self._initialized:
            return
        
        logger = get_logger(__name__)
        try:
            self.data_query = OptimizedStockDataQuery(self.db_path)
            self.backtest_engine = UnifiedBacktestEngine(self.data_query)
            self.stock_info_map = self.load_stock_info()
            self._initialized = True
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}", exc_info=True)
            raise
    
    def load_stock_info(self) -> Dict[str, str]:
        """
        【核心修复】使用 data_query 方法加载股票信息，支持 Polars + Parquet 后端
        """
        logger = get_logger(__name__)
        try:
            if self.data_query is None:
                return {}
            
            # 使用 data_query 的 _query_df 方法，支持 Polars 和 SQLite
            query = "SELECT stock_code, stock_name FROM stock_info"
            df = self.data_query._query_df(query)
            
            if df.empty:
                return {}
            
            # CHANGED: 确保 stock_code 是6位数字格式，作为字典的 key
            stock_info_dict = {}
            for _, row in df.iterrows():
                code = str(row['stock_code']).strip()
                name = str(row.get('stock_name', '')).strip()
                # 标准化为6位数字代码
                code_6 = code.zfill(6) if len(code) <= 6 else code[-6:]
                stock_info_dict[code_6] = name
            
            logger.debug(f"加载股票信息: {len(stock_info_dict)} 条记录")
            return stock_info_dict
        except Exception as e:
            logger.warning(f"加载股票信息失败: {e}")
            return {}
    
    def get_global_latest_factor(self, symbol_code: str) -> float:
        """
        【核心修复】获取该股票在数据库中最新（最后一天）的复权因子
        使用 data_query 方法，支持 Polars + Parquet 后端
        """
        logger = get_logger(__name__)
        try:
            if self.data_query is None:
                return 1.0
            
            # 使用 data_query 的 _query_df 方法，支持 Polars 和 SQLite
            query = """
                SELECT adj_factor 
                FROM stock_daily 
                WHERE stock_code = ? 
                ORDER BY trade_date DESC 
                LIMIT 1
            """
            df = self.data_query._query_df(query, [symbol_code])
            
            if df.empty or 'adj_factor' not in df.columns:
                return 1.0
            
            factor = df.iloc[0]['adj_factor']
            return float(factor) if factor is not None and not pd.isna(factor) else 1.0
        except Exception as e:
            logger.warning(f"获取最新复权因子失败 ({symbol_code}): {e}")
            return 1.0

