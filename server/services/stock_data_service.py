"""
股票数据服务
负责股票数据查询（K线、价格、股票信息、基准数据）
"""
from typing import Dict, List, Any, Optional
import pandas as pd
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from pathlib import Path
from server.utils.symbol_utils import normalize_symbol_code
from server.services.data_initialization_service import DataInitializationService
from config.logger import get_logger


class StockDataService:
    """股票数据服务类"""
    
    def __init__(self, init_service: DataInitializationService):
        self.init_service = init_service
    
    @property
    def data_query(self) -> Optional[OptimizedStockDataQuery]:
        """获取数据查询对象"""
        return self.init_service.data_query
    
    @property
    def stock_info_map(self) -> Dict[str, str]:
        """获取股票信息映射"""
        return self.init_service.stock_info_map
    
    def get_benchmark_data_from_db(self, benchmark_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取基准数据（需要数据库连接）"""
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()
        
        logger = get_logger(__name__)
        try:
            if self.data_query is None:
                self.init_service.ensure_initialized()
            
            if self.data_query is None:
                return pd.DataFrame()
            
            # 【核心修复】使用 data_query 方法，支持 DuckDB + Parquet 后端
            query = """
                SELECT date, close FROM benchmark_data
                WHERE code = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """
            df = self.data_query._query_df(query, [benchmark_code, start_date, end_date])
            
            if df.empty:
                logger.warning(f"在数据库中未找到基准数据: code={benchmark_code}, start={start_date}, end={end_date}")
                
            return df

        except Exception as e:
            logger.warning(f"读取基准数据时发生错误: {e}")
            return pd.DataFrame()
    
    def get_symbol_kline(self, symbol_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        获取K线数据（强制全局前复权）
        修复：不再使用区间内的最新因子，而是使用数据库里的全局最新因子。
        """
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()

        symbol_code = normalize_symbol_code(symbol_code)
        if not symbol_code:
            return []
        
        try:
            # 1. 获取原始数据 (Raw Price + Adj Factor)
            history_df = self.data_query.get_stock_history(
                symbol_code, start_date, end_date,
                columns=["stock_code", "trade_date", "open", "high", "low", "close", "volume", "adj_factor", "ma5", "ma10", "ma20"]
            )

            if history_df is None or history_df.empty:
                return []

            # 2. 【核心修复】获取全局最新因子作为基准
            base_factor = self.init_service.get_global_latest_factor(symbol_code)
            
            # 3. 计算前复权 (QFQ)
            # 公式：QFQ = Raw * (Current_Factor / Global_Latest_Factor)
            # 这样算出来的价格，才是和你现在看到的"现价"一致的价格
            history_df['qfq_ratio'] = history_df['adj_factor'] / base_factor
            
            price_cols = ['open', 'high', 'low', 'close', 'ma5', 'ma10', 'ma20']
            for col in price_cols:
                if col in history_df.columns:
                    history_df[col] = history_df[col] * history_df['qfq_ratio']

            # 4. 格式化输出
            records = []
            for _, row in history_df.iterrows():
                records.append({
                    "date": row['trade_date'],
                    "open": float(f"{row['open']:.2f}"),
                    "high": float(f"{row['high']:.2f}"),
                    "low": float(f"{row['low']:.2f}"),
                    "close": float(f"{row['close']:.2f}"),
                    "volume": float(row['volume']),
                    "ma5": float(f"{row['ma5']:.2f}") if pd.notna(row.get('ma5')) else None,
                    "ma10": float(f"{row['ma10']:.2f}") if pd.notna(row.get('ma10')) else None,
                    "ma20": float(f"{row['ma20']:.2f}") if pd.notna(row.get('ma20')) else None
                })
            return records
        except Exception as e:
            print(f"K线获取失败 {symbol_code}: {e}")
            return []
    
    def get_latest_prices(self, symbol_codes: List[str], target_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """获取最新价格（强制全局前复权）"""
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()

        if not symbol_codes:
            return {}

        normalized_codes = [normalize_symbol_code(c) for c in symbol_codes]
        latest_map = {}
        
        try:
            if self.data_query is None:
                return {}
            
            for code in set(normalized_codes):
                # 1. 获取全局最新因子（基准）
                base_factor = self.init_service.get_global_latest_factor(code)

                # 2. 查询目标日期的价格
                # 如果指定了 target_date，查那天的；没指定查最新一天的
                if target_date:
                    query = """
                        SELECT trade_date, open, close, prev_close, adj_factor 
                        FROM stock_daily 
                        WHERE stock_code = ? AND trade_date <= ?
                        ORDER BY trade_date DESC 
                        LIMIT 1
                    """
                    params = [code, target_date]
                else:
                    query = """
                        SELECT trade_date, open, close, prev_close, adj_factor 
                        FROM stock_daily 
                        WHERE stock_code = ?
                        ORDER BY trade_date DESC 
                        LIMIT 1
                    """
                    params = [code]
                
                df = self.data_query._query_df(query, params)
                if df.empty:
                    continue
                
                row = df.iloc[0]
                trade_date = row['trade_date']
                raw_open = row.get('open')
                raw_close = row.get('close')
                raw_prev = row.get('prev_close')
                current_factor = float(row.get('adj_factor', 1.0) or 1.0)
                
                # 3. 前复权计算，优先使用开盘价；没有开盘价时回退收盘价
                raw_price = raw_open if raw_open is not None and not pd.isna(raw_open) else raw_close
                if raw_price is None or pd.isna(raw_price):
                    continue
                ratio = current_factor / base_factor if base_factor else 1.0
                qfq_price = raw_price * ratio
                qfq_prev = (raw_prev * ratio) if raw_prev is not None and not pd.isna(raw_prev) else qfq_price

                latest_map[code] = {
                    "date": trade_date,
                    "price": float(f"{qfq_price:.2f}"),
                    "prev_close": float(f"{qfq_prev:.2f}")
                }
        except Exception as e:
            print(f"获取最新价格失败: {e}")
        return latest_map
    
    def get_stock_info_with_market_cap(self, needed_symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        获取股票基础信息（名称、市值）
        复用 OptimizedStockDataQuery 和 stock_info_map，避免重复查询
        
        Args:
            needed_symbols: 可选，如果提供则只查询这些股票，否则查询所有股票
        
        返回: {symbol: {name: str, market_cap: float}}
        """
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()
        
        logger = get_logger(__name__)
        stock_info = {}
        
        try:
            # 【核心修复】使用 data_query 方法，支持 DuckDB + Parquet 后端
            if self.data_query is None:
                return {}
            
            # CHANGED: 如果指定了需要的股票列表，只查询这些股票，大幅减少查询时间
            if needed_symbols:
                # 提取6位股票代码
                stock_codes = []
                for sym in needed_symbols:
                    # 处理 sz/sh 前缀
                    if sym.startswith(('sz', 'sh')):
                        code = sym[2:]  # 去掉 sz/sh 前缀
                    else:
                        code = sym
                    # 提取6位数字代码
                    if len(code) >= 6:
                        code_6 = code[-6:].zfill(6)  # 确保是6位
                        stock_codes.append(code_6)
                    elif len(code) == 6:
                        stock_codes.append(code.zfill(6))
                
                logger.debug(f"从 needed_symbols 提取的股票代码: {needed_symbols} -> {stock_codes}")
                
                if stock_codes:
                    # 使用 IN 查询，只查询需要的股票
                    placeholders = ','.join(['?' for _ in stock_codes])
                    query = f"""
                        SELECT 
                            stock_code,
                            MAX(total_mv) as market_cap
                        FROM stock_daily
                        WHERE total_mv IS NOT NULL
                            AND stock_code IN ({placeholders})
                        GROUP BY stock_code
                    """
                    df = self.data_query._query_df(query, stock_codes)
                    logger.debug(f"市值查询结果: {len(df)} 条记录")
                else:
                    df = pd.DataFrame()
                    logger.warning(f"无法从 needed_symbols 提取有效的股票代码: {needed_symbols}")
            else:
                # 获取每只股票的最新市值（取最新交易日的市值）
                query = """
                    SELECT 
                        stock_code,
                        MAX(total_mv) as market_cap
                    FROM stock_daily
                    WHERE total_mv IS NOT NULL
                    GROUP BY stock_code
                """
                df = self.data_query._query_df(query)
            
            for _, row in df.iterrows():
                symbol_code = str(row['stock_code']).zfill(6)
                market_cap = float(row['market_cap'] or 0.0) / 10000.0  # 万元转亿元
                
                # 构建标准股票代码
                if symbol_code.startswith('0'):
                    full_symbol = f"sz{symbol_code}"
                elif symbol_code.startswith('6'):
                    full_symbol = f"sh{symbol_code}"
                else:
                    full_symbol = symbol_code
                
                # CHANGED: 从 stock_info_map 获取名称（已加载）
                stock_name = self.stock_info_map.get(symbol_code, '')
                
                # 如果 stock_info_map 中没有名称，尝试从 data_query 查询
                if not stock_name and self.data_query is not None:
                    try:
                        name_query = "SELECT stock_name FROM stock_info WHERE stock_code = ?"
                        name_df = self.data_query._query_df(name_query, [symbol_code])
                        if not name_df.empty and 'stock_name' in name_df.columns:
                            stock_name = str(name_df.iloc[0]['stock_name']) or ''
                    except Exception as e:
                        logger.debug(f"查询股票名称失败: {symbol_code}, 错误: {e}")
                
                logger.debug(f"股票信息: {full_symbol} (代码: {symbol_code}) -> 名称: {stock_name or '(空)'}")
                
                stock_info[full_symbol] = {
                    'name': stock_name,
                    'market_cap': market_cap,
                    'original_code': symbol_code
                }
        except Exception as e:
            logger.warning(f"从数据库获取股票市值失败，尝试 Parquet: {e}")
            
            # 回退：尝试从 Parquet 读取
            try:
                try:
                    import duckdb
                except ImportError:
                    duckdb = None
                
                if duckdb is not None:
                    base_dir = Path(__file__).parent.parent
                    stock_daily_parquet = base_dir / 'parquet_data' / 'stock_daily.parquet'
                    stock_info_parquet = base_dir / 'parquet_data' / 'stock_info.parquet'
                    
                    if stock_daily_parquet.exists():
                        stock_daily_str = str(stock_daily_parquet).replace('\\', '/')
                        
                        # CHANGED: 如果指定了需要的股票列表，添加过滤条件
                        if needed_symbols:
                            stock_codes = []
                            for sym in needed_symbols:
                                code = sym[2:] if sym.startswith(('sz', 'sh')) else sym
                                if len(code) >= 6:
                                    stock_codes.append(code[-6:])
                            
                            if stock_codes:
                                codes_str = "', '".join(stock_codes)
                                code_filter = f"AND d.stock_code IN ('{codes_str}')"
                            else:
                                code_filter = ""
                        else:
                            code_filter = ""
                        
                        if stock_info_parquet.exists():
                            stock_info_str = str(stock_info_parquet).replace('\\', '/')
                            sql = f"""
                                SELECT
                                    d.stock_code,
                                    COALESCE(CAST(i.stock_name AS VARCHAR), '') AS stock_name,
                                    MAX(d.total_mv) AS market_cap
                                FROM read_parquet('{stock_daily_str}') d
                                LEFT JOIN read_parquet('{stock_info_str}') i ON d.stock_code = i.stock_code
                                WHERE d.total_mv IS NOT NULL
                                    {code_filter}
                                GROUP BY d.stock_code, i.stock_name
                            """
                        else:
                            sql = f"""
                                SELECT
                                    stock_code,
                                    '' AS stock_name,
                                    MAX(total_mv) AS market_cap
                                FROM read_parquet('{stock_daily_str}')
                                WHERE total_mv IS NOT NULL
                                    {code_filter}
                                GROUP BY stock_code
                            """
                        
                        con = duckdb.connect()
                        try:
                            # CHANGED: 设置 DuckDB 性能参数
                            try:
                                con.execute("SET threads TO 4")
                            except Exception:
                                pass
                            try:
                                con.execute("SET memory_limit='2GB'")
                            except Exception:
                                pass
                            
                            df_stock = con.execute(sql).df()
                            for _, row in df_stock.iterrows():
                                symbol_code = str(row.get('stock_code')).zfill(6)
                                stock_name = row.get('stock_name') or ''
                                market_cap = float(row.get('market_cap') or 0.0) / 10000.0
                                
                                if symbol_code.startswith('0'):
                                    full_symbol = f"sz{symbol_code}"
                                elif symbol_code.startswith('6'):
                                    full_symbol = f"sh{symbol_code}"
                                else:
                                    full_symbol = symbol_code
                                
                                # 如果从 Parquet 获取的名称为空，尝试从 stock_info_map 或 data_query 获取
                                if not stock_name:
                                    stock_name = self.stock_info_map.get(symbol_code, '')
                                    # 如果 stock_info_map 也没有，尝试从 data_query 查询
                                    if not stock_name and self.data_query is not None:
                                        try:
                                            name_query = "SELECT stock_name FROM stock_info WHERE stock_code = ?"
                                            name_df = self.data_query._query_df(name_query, [symbol_code])
                                            if not name_df.empty and 'stock_name' in name_df.columns:
                                                stock_name = str(name_df.iloc[0]['stock_name']) or ''
                                        except Exception:
                                            pass  # 如果查询失败，保持空名称
                                
                                stock_info[full_symbol] = {
                                    'name': stock_name,
                                    'market_cap': market_cap,
                                    'original_code': symbol_code
                                }
                        finally:
                            con.close()
            except Exception as e2:
                logger.warning(f"从 Parquet 获取股票信息也失败: {e2}")
        
        return stock_info

