import json
import pandas as pd
try:
    import cupy as np
except ImportError:
    import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Generator
from threading import Event
from database.optimized_data_query import OptimizedStockDataQuery
from backtest.optimized_backtest_engine import OptimizedBacktestEngine
from strategies.strategy_factory import StrategyFactory
import sqlite3
import os
import sys
from pathlib import Path
import re

# 添加项目根目录到 Python 路径
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.config import Config  # type: ignore

class BacktestVisualizationAPI:
    """回测数据可视化API接口"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DB_PATH
        self.data_query: Optional[OptimizedStockDataQuery] = None
        self.backtest_engine: Optional[OptimizedBacktestEngine] = None
        self.stock_info_map: Dict[str, str] = {}
        self._initialized = False
        self.initial_capital = Config.INITIAL_CAPITAL

    @staticmethod
    def _normalize_symbol_code(symbol_code: Optional[str]) -> str:
        if not symbol_code: return ''
        code = str(symbol_code).strip().upper()
        match = re.search(r'(\d{6})', code)
        return match.group(1) if match else code
    
    def _ensure_initialized(self) -> None:
        if self._initialized: return
        from utils.logger import get_logger
        logger = get_logger(__name__)
        try:
            self.data_query = OptimizedStockDataQuery(self.db_path)
            self.backtest_engine = OptimizedBacktestEngine(self.data_query)
            self.stock_info_map = self._load_stock_info()
            self._initialized = True
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}", exc_info=True)
            raise

    def _load_stock_info(self) -> Dict[str, str]:
        try:
            db_uri = f'file:{self.db_path}?mode=ro'
            with sqlite3.connect(db_uri, uri=True) as conn:
                cursor = conn.cursor()
                # 检查列名是否存在，防止报错
                cursor.execute("PRAGMA table_info(stock_info)")
                columns = [info[1] for info in cursor.fetchall()]
                
                name_col = 'stock_name' if 'stock_name' in columns else 'name'
                code_col = 'stock_code' if 'stock_code' in columns else 'symbol'
                
                if name_col not in columns or code_col not in columns:
                    return {}

                df = pd.read_sql_query(f"SELECT {code_col}, {name_col} FROM stock_info", conn)
                return pd.Series(df[name_col].values, index=df[code_col].astype(str)).to_dict()
        except Exception:
            return {}
    def _get_global_latest_factor(self, symbol_code: str) -> float:
        """【关键】获取该股票在数据库中最新（最后一天）的复权因子"""
        try:
            # 直接使用 SQL 查询，比 pandas 更快
            db_uri = f'file:{self.db_path}?mode=ro'
            with sqlite3.connect(db_uri, uri=True) as conn:
                cursor = conn.cursor()
                # 按日期倒序查第一条，确保拿到的是该股票整个生命周期里最新的因子
                cursor.execute(
                    "SELECT adj_factor FROM stock_daily WHERE stock_code = ? ORDER BY trade_date DESC LIMIT 1", 
                    (symbol_code,)
                )
                row = cursor.fetchone()
                return float(row[0]) if row and row[0] is not None else 1.0
        except Exception:
            return 1.0
    # --- 【【新增】】统一的前复权计算工具函数 ---
    def _calculate_qfq_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将 DataFrame 中的价格列转换为前复权 (QFQ) 价格
        逻辑：QFQ = Raw * (AdjFactor / LatestFactor)
        
        使用这段时间内的最新复权因子作为基准，确保价格序列平滑连续
        """
        if df is None or df.empty or 'adj_factor' not in df.columns:
            return df
        
        df = df.copy()
        
        # 获取这批数据中，每只股票的"最新"复权因子（作为基准）
        # 按 stock_code 分组，找到每只股票的最新因子（trade_date 最大的那个）
        if 'trade_date' in df.columns:
            # 按股票代码分组，找到每只股票的最新因子
            latest_factors = df.groupby('stock_code').apply(
                lambda g: g.loc[g['trade_date'].idxmax(), 'adj_factor']
            )
            # 将最新因子映射回原 DataFrame
            df['latest_factor'] = df['stock_code'].map(latest_factors)
        else:
            # 如果没有 trade_date，使用每组的最后一个因子
            latest_factors = df.groupby('stock_code')['adj_factor'].transform('last')
            df['latest_factor'] = latest_factors
        
        # 计算复权比率 (防止除零)
        df['latest_factor'] = df['latest_factor'].replace(0, 1.0)
        qfq_ratio = df['adj_factor'] / df['latest_factor']
        
        # 应用到价格列
        price_cols = ['open', 'high', 'low', 'close', 'prev_close', 'ma5', 'ma10', 'ma20', 'ma60']
        for col in price_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') * qfq_ratio
        
        # 清理临时列
        df.drop(columns=['latest_factor'], inplace=True, errors='ignore')
        
        return df

    def get_strategy_list(self) -> List[Dict]:
        """获取策略列表（不需要数据库连接）"""
        strategies = []
        try:
            print("[DEBUG] 开始获取策略列表...")
            
            # 直接导入并使用get_factory函数
            from strategies.strategy_factory import get_factory
            print("[DEBUG] 导入策略工厂的get_factory函数")
            
            factory = get_factory()
            print(f"[DEBUG] 获取到策略工厂实例: {factory}")
            
            # 使用list_strategies方法获取更详细的策略信息
            strategy_info_list = factory.list_strategies()
            print(f"[DEBUG] 从策略工厂获取到 {len(strategy_info_list)} 个策略")
            print(f"[DEBUG] 策略工厂返回的策略信息: {strategy_info_list}")
            
            # 确保strategy_info_list是列表类型
            if not isinstance(strategy_info_list, list):
                print(f"[ERROR] 策略工厂返回的不是列表，而是: {type(strategy_info_list)}")
                return []
            
            for idx, strategy_info in enumerate(strategy_info_list):
                print(f"[DEBUG] 处理策略 {idx+1}: {strategy_info}")
                
                # 安全地获取策略信息
                strategy_id = strategy_info.get('name', '')
                class_name = strategy_info.get('class_name', '')
                
                # 如果name为空，尝试使用class_name
                if not strategy_id and class_name:
                    strategy_id = class_name
                    print(f"[DEBUG] 使用class_name作为strategy_id: {class_name}")
                
                if not strategy_id:
                    print(f"[DEBUG] 跳过没有名称的策略: {strategy_info}")
                    continue
                
                strategy_name = strategy_id  # 使用名称作为ID和名称
                
                # 创建策略字典并添加到结果列表
                strategy_dict = {
                    "id": strategy_id,
                    "name": strategy_name,
                    "description": f"{strategy_name}的描述",
                    "createdDate": "2024-01-01",
                    "lastUpdated": "2024-01-01",
                    "performance": 0.0,
                    "status": "active"
                }
                strategies.append(strategy_dict)
                print(f"[DEBUG] 添加策略到结果列表: {strategy_dict}")
            
            print(f"[DEBUG] 最终返回 {len(strategies)} 个策略")
            return strategies
        except Exception as e:
            print(f"[ERROR] 获取策略列表失败: {e}")
            import traceback
            traceback.print_exc()
            return []  # 返回空列表而不是报错
    
    def get_strategy_logic(self, strategy_id: str) -> Dict[str, Any]:
        """
        获取策略的逻辑描述
        【优化】直接读取策略类的 DocString，不再维护硬编码字典
        """
        try:
            strategy_class = StrategyFactory.get_factory().get_strategy_by_name(strategy_id)
            if not strategy_class:
                return {"buy_logic": "策略未找到", "sell_logic": "", "description": ""}
            
            # 1. 优先尝试调用策略类的 get_logic_description 方法 (如果你实现了的话)
            if hasattr(strategy_class, "get_logic_description"):
                return strategy_class.get_logic_description()

            # 2. 否则自动解析 Python 文档注释 (__doc__)
            doc = strategy_class.__doc__ or "暂无描述"
            
            # 简单粗暴的解析：假设文档里写了 "买入逻辑：" 和 "卖出逻辑："
            # 如果没写，就全部丢给 description
            return {
                "buy_logic": "请在策略代码类注释中补充买入逻辑...", # 前端兼容占位
                "sell_logic": "请在策略代码类注释中补充卖出逻辑...", 
                "description": doc.strip()
            }
        except Exception as e:
            print(f"获取策略逻辑失败: {e}")
            return {"buy_logic": "获取失败", "sell_logic": "", "description": ""}
    
    def get_strategy_params(self, strategy_id: str) -> list[dict]:
        """
        返回给前端用的参数列表。
        【优化】彻底移除 param_metadata 映射和 default_min/max 猜测逻辑。
        只有策略类明确说了范围 (get_param_spec) 才返回，否则一律 None，由前端接管。
        """
        # 1. 找到策略类
        strategy_class = StrategyFactory.get_factory().get_strategy_by_name(strategy_id)
        if strategy_class is None:
            raise ValueError(f"未找到策略：{strategy_id}")

        # 2. 优先使用策略类提供的 PARAM_SPEC
        if hasattr(strategy_class, "get_param_spec"):
            spec = strategy_class.get_param_spec()
            if spec:
                # 完全放权给前端：不返回 min/max，让前端自主决定搜索范围
                return [
                    {
                        "key": item["key"],
                        "label": item.get("label", item["key"]),
                        "group": item.get("group", "其它"),
                        "type": item.get("type", "float"),
                        "min": None,  # 不返回范围限制，完全由前端控制
                        "max": None,  # 不返回范围限制，完全由前端控制
                        "step": item.get("step"),
                        "default": item.get("default"),
                        "optimize": item.get("optimize", True),
                        "description": item.get("description", ""),
                    }
                    for item in spec
                ]

        # 3. 退回 dataclass 自动推断 (旧式策略)
        strategy = StrategyFactory.get_factory().create_strategy(strategy_id)
        if hasattr(strategy, "config"):
            from dataclasses import is_dataclass, asdict

            config = strategy.config
            if is_dataclass(config):
                config_dict = asdict(config)
            elif isinstance(config, dict):
                config_dict = config
            else:
                return []

            params = []
            
            for field_name, field_value in config_dict.items():
                # 跳过非优化参数
                if isinstance(field_value, (list, dict)) or field_name.startswith('_'):
                    continue
                
                param_type = 'int' if isinstance(field_value, int) else 'float'
                
                # 【核心修改】不再去查 metadata_map，也不再去猜 min/max
                # 直接告诉前端：我有这个参数，默认值是多少，剩下的你看着办
                params.append({
                    "key": field_name,
                    "label": field_name, # 没有label就直接用key
                    "type": param_type,
                    "min": None, 
                    "max": None,
                    "default": field_value,
                    "description": ""
                })
            return params

        # 4. 实在啥都没有，就返回空
        return []
    
    def _get_benchmark_data_from_db(self, benchmark_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取基准数据（需要数据库连接）"""
        if not self._initialized:
            self._ensure_initialized()
        
        try:
            if not os.path.exists(self.db_path):
                from utils.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"数据库文件未找到: {self.db_path}")
                return pd.DataFrame()
                
            db_uri = f'file:{self.db_path}?mode=ro'
            with sqlite3.connect(db_uri, uri=True) as conn:
                # CHANGED: 应用只读连接的性能优化
                from database.db_utils import apply_performance_pragmas
                apply_performance_pragmas(conn, read_only=True)
                
                query = """
                    SELECT date, close FROM benchmark_data
                    WHERE code = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """
                df = pd.read_sql_query(query, conn, params=(benchmark_code, start_date, end_date))
            
            if df.empty:
                print(f"在数据库中未找到基准数据: code={benchmark_code}, start={start_date}, end={end_date}")
                
            return df

        except sqlite3.OperationalError as e:
            print(f"查询基准数据时发生数据库错误: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"读取基准数据时发生未知错误: {e}")
            return pd.DataFrame()

    
    # --- 【【代码还原】】: 还原旧的、阻塞的 API 函数 (作为备用) ---
    def get_symbol_kline(self, symbol_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        获取K线数据（强制全局前复权）
        修复：不再使用区间内的最新因子，而是使用数据库里的全局最新因子。
        """
        if not self._initialized:
            self._ensure_initialized()

        symbol_code = self._normalize_symbol_code(symbol_code)
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
            base_factor = self._get_global_latest_factor(symbol_code)
            
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
        if not self._initialized:
            self._ensure_initialized()

        if not symbol_codes:
            return {}

        normalized_codes = [self._normalize_symbol_code(c) for c in symbol_codes]
        latest_map = {}
        
        try:
            db_uri = f'file:{self.db_path}?mode=ro'
            with sqlite3.connect(db_uri, uri=True) as conn:
                for code in set(normalized_codes):
                    # 1. 获取全局最新因子（基准）
                    base_factor = self._get_global_latest_factor(code)

                    # 2. 查询目标日期的价格
                    # 如果指定了 target_date，查那天的；没指定查最新一天的
                    query_date_clause = "AND trade_date <= ?" if target_date else ""
                    params = (code, target_date) if target_date else (code,)
                    
                    query = f"""
                        SELECT trade_date, open, close, prev_close, adj_factor 
                        FROM stock_daily 
                        WHERE stock_code = ? {query_date_clause}
                        ORDER BY trade_date DESC 
                        LIMIT 1
                    """
                    cursor = conn.execute(query, params)
                    result = cursor.fetchone()
                    
                    if result:
                        trade_date, raw_open, raw_close, raw_prev, current_factor = result
                        current_factor = float(current_factor or 1.0)
                        
                        # 3. 前复权计算，优先使用开盘价；没有开盘价时回退收盘价
                        raw_price = raw_open if raw_open is not None else raw_close
                        if raw_price is None:
                            continue
                        ratio = current_factor / base_factor if base_factor else 1.0
                        qfq_price = raw_price * ratio
                        qfq_prev = (raw_prev * ratio) if raw_prev else raw_price

                        latest_map[code] = {
                            "date": trade_date,
                            "price": float(f"{qfq_price:.2f}"),
                            "prev_close": float(f"{qfq_prev:.2f}")
                        }
        except Exception as e:
            print(f"获取最新价格失败: {e}")
        return latest_map

    def run_backtest_and_get_data(self, strategy_name: str, start_date: str, end_date: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """
        运行回测并获取数据（真实数据，作为备用）
        CHANGED: 使用流式回测并收集结果
        """
        if not self._initialized:
            self._ensure_initialized()

        # 为每次回测创建独立的数据查询和回测引擎，避免并发共享同一个 DuckDB 连接导致异常
        local_data_query = OptimizedStockDataQuery(self.db_path)
        local_engine = OptimizedBacktestEngine(local_data_query)
        
        try:
            creation_kwargs: Dict[str, Any] = params or {}
            strategy = StrategyFactory.create_strategy(strategy_name, use_simple=True, **creation_kwargs)
            
            # CHANGED: 使用流式回测并收集所有结果
            results_list = []
            trades_log = []
            final_metrics = None
            
            # 运行流式回测并收集数据（使用本地引擎，线程隔离）
            for update in local_engine.run_backtest_streaming(start_date, end_date, strategy):
                update_type = update.get('type')
                data = update.get('data', {})
            
                if update_type == 'daily_equity_engine':
                    results_list.append({
                        'date': data.get('date'),
                        'total_value': data.get('strategyReturn', 0)
                    })
                elif update_type == 'new_trade_engine':
                    # CHANGED: 收集完整的交易记录，包括所有字段
                    trade = {
                        'date': data.get('date'),
                        'symbol': data.get('symbol') or data.get('symbol_code', ''),
                        'action': data.get('action'),
                        'price': data.get('price', 0),
                        'quantity': data.get('quantity', 0),
                        'commission': data.get('commission', 0),
                        'entry_date': data.get('entry_date'),
                        'exit_date': data.get('exit_date'),
                        'position_id': data.get('position_id')
                    }
                    trades_log.append(trade)
                elif update_type == 'final_metrics':
                    final_metrics = data
                elif update_type == 'error':
                    error_msg = data.get('message', '回测发生错误')
                    return {"error": error_msg}
            
            # 转换为 DataFrame
            if not results_list:
                error_msg = (
                    f"回测没有产生任何结果。\n\n"
                    f"请检查数据库 '{self.db_path}' 中 "
                    f"是否存在 {start_date} 到 {end_date} 期间的股票数据。"
                )
                return {"error": error_msg}
            
            results_df = pd.DataFrame(results_list)
            results_df['date'] = pd.to_datetime(results_df['date'])
            results_df = results_df.sort_values('date')
            
            # 使用收集到的指标或计算指标
            if final_metrics:
                metrics = final_metrics
            else:
                metrics = self._calculate_metrics_from_df(results_df, trades_log)
            
            # 调用转换函数
            return self._convert_backtest_results(
                results_df, trades_log, strategy.name, start_date, end_date
            )
        except Exception as e:
            print(f"运行回测错误: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            try:
                local_data_query.close()
            except Exception:
                pass
    
    def _convert_backtest_results(self, results_df: pd.DataFrame, trades_log: List[Dict], 
                                 strategy_name: str, start_date: str, end_date: str) -> Dict:
        """
        (此函数保持不变, 作为备用)
        转换回测结果
        """
        
        metrics = self._calculate_metrics_from_df(results_df, trades_log)
        equity_curve = self._extract_equity_curve_from_df(results_df)
        risk_data = self._calculate_risk_from_df(results_df)
        
        # (格式化交易记录)
        paged_trades = trades_log[:10]
        formatted_trades = []
        positions = {}
        cumulative_pnl = 0
        
        for trade in reversed(trades_log): 
            symbol = trade['symbol']
            qty = trade['quantity']
            price = trade['price']
            action = trade['action']
            pnl = 0
            
            if action == 'buy':
                if symbol not in positions:
                    positions[symbol] = {'qty': 0, 'cost': 0}
                positions[symbol]['cost'] = (positions[symbol]['cost'] * positions[symbol]['qty'] + qty * price) / (positions[symbol]['qty'] + qty)
                positions[symbol]['qty'] += qty
            elif action == 'sell':
                if symbol in positions and positions[symbol]['qty'] > 0:
                    avg_cost = positions[symbol].get('cost', price)
                    pnl = (price - avg_cost) * qty
                    cumulative_pnl += pnl
                    positions[symbol]['qty'] -= qty
            
            trade['profitLoss'] = pnl
            trade['cumulativePnL'] = cumulative_pnl

        trades_log.reverse()
        # CHANGED: 返回所有交易记录，而不是只返回前10条
        for trade in trades_log:
             raw_symbol_code = self._normalize_symbol_code(trade.get('symbol') or trade.get('symbol_code', ''))
             entry_date = trade.get('entry_date')
             exit_date = trade.get('exit_date')
             
             # CHANGED: 计算持有周期（天数）
             holding_days = None
             if entry_date and exit_date:
                 try:
                     from datetime import datetime
                     entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                     exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
                     holding_days = (exit_dt - entry_dt).days
                 except:
                     pass
             elif entry_date and trade['action'] == 'sell':
                 try:
                     from datetime import datetime
                     entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                     trade_dt = datetime.strptime(trade['date'], '%Y-%m-%d')
                     holding_days = (trade_dt - entry_dt).days
                 except:
                     pass
             
             # CHANGED: 手续费为万分之五，不足五元按五元算
             commission_base = trade.get('commission', trade['price'] * trade['quantity'] * 0.0005)
             commission = max(commission_base, 5.0) if commission_base > 0 else 5.0
             
             # CHANGED: 提取 FIFO 匹配的结果（如果存在）
             # 优先使用回测引擎计算好的精确值，防止前端再次计算出错
             entry_price = trade.get('entry_price')
             exit_price = trade.get('exit_price')
             profit_loss = trade.get('profit_loss')
             roi = trade.get('roi')
             holding_days_from_engine = trade.get('holding_days')
             
             # 如果引擎提供了持有周期，优先使用
             if holding_days_from_engine is not None:
                 holding_days = holding_days_from_engine
             
             formatted_trades.append({
                "id": f"trade-{trade['date']}-{raw_symbol_code}-{trade['action']}",
                "date": trade['date'],
                "symbol": self.stock_info_map.get(raw_symbol_code, raw_symbol_code), # <-- 修复了股票名称
                "symbolCode": raw_symbol_code,  # <--- Add this
                "symbol_code": raw_symbol_code, # <--- Add this for safety
                "action": trade['action'],
                "price": trade['price'],  # 前复权价格（来自回测引擎）
                "quantity": trade['quantity'],
                "value": trade.get('price', 0) * trade.get('quantity', 0),
                "commission": commission,
                "profitLoss": profit_loss if profit_loss is not None else trade.get('profitLoss', 0),
                "cumulativePnL": trade.get('cumulativePnL', 0),
                "entryDate": entry_date,
                "exitDate": exit_date,
                "entry_price": entry_price,  # CHANGED: FIFO 匹配的开仓价
                "exit_price": exit_price,  # CHANGED: FIFO 匹配的平仓价
                "profit_loss": profit_loss,  # CHANGED: FIFO 计算的盈亏
                "roi": roi,  # CHANGED: FIFO 计算的收益率
                "positionId": trade.get('position_id'),
                "holdingDays": holding_days  # CHANGED: 持有周期（天数）
            })

        trade_records_data = {
            "trades": formatted_trades,
            "total": len(trades_log),
        }

        # 实际回测使用的日期范围（可能已被引擎自动截断到数据库可用范围）
        actual_start = pd.to_datetime(results_df['date']).min().strftime('%Y-%m-%d') if not results_df.empty else start_date
        actual_end = pd.to_datetime(results_df['date']).max().strftime('%Y-%m-%d') if not results_df.empty else end_date

        return {
            "versionId": strategy_name,  # 添加 versionId 字段
            "strategyInfo": {
                "name": strategy_name,
                "description": f"{strategy_name}回测结果",
                "period": f"{actual_start} 至 {actual_end}",
                "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "metrics": metrics,  # CHANGED: 使用 metrics 而不是 performanceMetrics
            "performanceMetrics": metrics,  # 保留兼容性
            # CHANGED: equityCurve 应该是包含 date 和 equity 的对象数组
            "equityCurve": [
                {
                    "date": date,
                    "equity": equity,
                    "benchmarkEquity": benchmark_equity if "benchmarkReturns" in equity_curve else None
                }
                for date, equity, benchmark_equity in zip(
                    equity_curve.get("dates", []),
                    equity_curve.get("strategyReturns", []),
                    equity_curve.get("benchmarkReturns", [])
                )
            ],
            "equityCurveData": equity_curve,  # 保留完整数据
            "actualStartDate": actual_start,
            "actualEndDate": actual_end,
            "monthlyReturns": risk_data.get("monthlyReturns", []),  # CHANGED: 添加 monthlyReturns
            "riskAnalysisData": risk_data,
            "trades": formatted_trades,  # CHANGED: 直接返回 trades 数组，而不是 tradeRecords
            "tradeRecords": trade_records_data  # 保留兼容性
        }

    def _calculate_metrics_from_df(self, results_df: pd.DataFrame, trades_log: List[Dict]) -> Dict:
            """ 用于流式回测的最终指标计算 """
            initial_capital = self.initial_capital
            final_value = results_df['total_value'].iloc[-1]
            total_return = (final_value / initial_capital - 1) * 100

            days = len(results_df)
            years = days / 252.0
            annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else total_return

            results_df['cummax'] = results_df['total_value'].cummax()
            results_df['drawdown'] = (results_df['total_value'] - results_df['cummax']) / results_df['cummax']
            max_drawdown = results_df['drawdown'].min() * 100

            # 日收益率
            daily_returns = results_df['total_value'].pct_change().dropna()
            if len(daily_returns) > 1:
                dr_mean = daily_returns.mean()
                dr_std = daily_returns.std()
                sharpe_ratio = (dr_mean / dr_std) * np.sqrt(252) if dr_std > 0 else 0

                downside_returns = daily_returns[daily_returns < 0]
                if len(downside_returns) > 0:
                    downside_std = downside_returns.std()
                    sortino_ratio = (dr_mean / downside_std) * np.sqrt(252) if downside_std > 0 else 0
                else:
                    sortino_ratio = 0

                volatility = dr_std * np.sqrt(252) * 100  # 年化波动率（%）
            else:
                sharpe_ratio = 0
                sortino_ratio = 0
                volatility = 0

            # 交易统计
            trades_count = len(trades_log)
            win_trades = 0
            total_pnl = 0
            total_profit = 0
            total_loss = 0

            max_win_streak = 0
            max_loss_streak = 0
            current_win_streak = 0
            current_loss_streak = 0

            sum_trade_return_pct = 0.0  # 用来算“平均每笔收益率（%）”

            positions: Dict[str, Dict[str, float]] = {}
            for trade in trades_log:
                action = trade['action']
                symbol = str(trade['symbol'])
                qty = trade['quantity']
                price = trade['price']

                if action == 'sell':
                    avg_cost = positions.get(symbol, {}).get('cost', price)
                    pnl = (price - avg_cost) * qty

                    # 统计盈亏次数 & 盈利/亏损总额
                    if pnl > 0:
                        win_trades += 1
                        total_profit += pnl
                        current_win_streak += 1
                        max_win_streak = max(max_win_streak, current_win_streak)
                        current_loss_streak = 0
                    elif pnl < 0:
                        total_loss += abs(pnl)
                        current_loss_streak += 1
                        max_loss_streak = max(max_loss_streak, current_loss_streak)
                        current_win_streak = 0
                    else:
                        current_win_streak = 0
                        current_loss_streak = 0

                    total_pnl += pnl

                    # 单笔收益率（相对于成本）
                    exposure = avg_cost * qty
                    if exposure > 0:
                        trade_return_pct = (pnl / exposure) * 100
                        sum_trade_return_pct += trade_return_pct

                elif action == 'buy':
                    if symbol not in positions:
                        positions[symbol] = {'qty': 0, 'cost': 0}
                    prev_qty = positions[symbol]['qty']
                    prev_cost = positions[symbol]['cost']

                    new_qty = prev_qty + qty
                    new_cost = (prev_cost * prev_qty + qty * price) / new_qty if new_qty > 0 else price

                    positions[symbol]['qty'] = new_qty
                    positions[symbol]['cost'] = new_cost

            sell_trades_count = len([t for t in trades_log if t['action'] == 'sell'])
            win_rate = (win_trades / sell_trades_count) * 100 if sell_trades_count > 0 else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else 0
            avg_trade_return = (sum_trade_return_pct / sell_trades_count) if sell_trades_count > 0 else 0

            def _to_scalar(x: Any) -> float:
                try:
                    if isinstance(x, (int, float)):
                        return float(x)
                    arr = np.asarray(x)
                    if arr.shape == ():
                        return float(arr)
                    return float(arr.mean())
                except Exception:
                    return 0.0

            total_return_v = _to_scalar(total_return)
            annualized_return_v = _to_scalar(annualized_return)
            max_drawdown_v = _to_scalar(max_drawdown)
            sharpe_ratio_v = _to_scalar(sharpe_ratio)
            sortino_ratio_v = _to_scalar(sortino_ratio)
            volatility_v = _to_scalar(volatility)
            win_rate_v = _to_scalar(win_rate)
            profit_factor_v = _to_scalar(profit_factor)
            avg_trade_return_v = _to_scalar(avg_trade_return)

            # Calmar 比率 = 年化收益率 / |最大回撤|
            calmar_ratio_v = 0.0
            if abs(max_drawdown_v) > 1e-8:
                calmar_ratio_v = annualized_return_v / abs(max_drawdown_v)

            return {
                "totalReturn": round(total_return_v, 2),
                "annualizedReturn": round(annualized_return_v, 2),
                "maxDrawdown": round(abs(max_drawdown_v), 2),
                "sharpeRatio": round(sharpe_ratio_v, 2),
                "sortinoRatio": round(sortino_ratio_v, 2),
                "volatility": round(volatility_v, 2),
                "winRate": round(win_rate_v, 1),
                "profitFactor": round(profit_factor_v, 2),
                "tradesCount": trades_count,
                "avgTradeReturn": round(avg_trade_return_v, 2),       # 【注意】驼峰命名，单位 %
                "maxWinningStreak": int(max_win_streak),
                "maxLosingStreak": int(max_loss_streak),
                "calmarRatio": round(calmar_ratio_v, 3),
            }


    def _extract_equity_curve_from_df(self, results_df: pd.DataFrame) -> Dict:
        """
        (此函数保持不变, 作为备用)
        CHANGED: 确保数据库已初始化
        """
        if not self._initialized:
            self._ensure_initialized()
        
        initial_capital = self.backtest_engine.initial_capital
        # (我们在这里也修复一下基准，让它查询数据库)
        # 将日期统一格式化为字符串，避免 pandas.Timestamp 直接传入 SQL 参数
        date_series = pd.to_datetime(results_df['date'])
        dates = date_series.dt.strftime('%Y-%m-%d').tolist()
        start_date_str = dates[0]
        end_date_str = dates[-1]
        benchmark_df = self._get_benchmark_data_from_db('000300', start_date_str, end_date_str)
        benchmark_curve = []

        if not benchmark_df.empty:
             try:
                strategy_dates_df = pd.DataFrame({'date': dates})
                merged_df = pd.merge(strategy_dates_df, benchmark_df, on='date', how='left')
                merged_df['close'] = merged_df['close'].ffill().bfill()
                first_valid_benchmark = merged_df['close'].dropna().iloc[0]
                if first_valid_benchmark > 0:
                    normalized_curve = (merged_df['close'] / first_valid_benchmark) * initial_capital
                    benchmark_curve = normalized_curve.fillna(initial_capital).tolist()
             except: pass # (忽略错误)
        
        if not benchmark_curve:
             benchmark_curve = np.linspace(initial_capital, initial_capital, len(results_df)).tolist() 

        return {
            "dates": dates,
            "strategyReturns": results_df['total_value'].tolist(),
            "benchmarkReturns": benchmark_curve
        }
    
    def _calculate_risk_from_df(self, results_df: pd.DataFrame) -> Dict:
        if results_df is None or results_df.empty:
            return {
                "drawdowns": [],
                "volatility": [],
                "returnDistribution": [],
                "monthlyReturns": []
            }
        # 1. 规范化基础数据
        df = results_df.copy()

        # 只保留我们关心的两列
        if 'total_value' not in df.columns:
            # 兜底：如果有 equity 或类似字段，可以在这里做一层映射
            raise ValueError("results_df 缺少 total_value 列，无法计算风险指标")

        df = df[['date', 'total_value']].copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 2. 从 total_value 计算逐日回撤
        df['cummax'] = df['total_value'].cummax()
        # drawdown 是一个负数（回撤），比如 -0.15 = 回撤 15%
        df['drawdown'] = df['total_value'] / df['cummax'] - 1.0

        # 3. 最大回撤 Top 5（按回撤深度排序，取最深的前 5 个点）
        drawdown_data = []
        drawdowns = df[df['drawdown'] < 0][['date', 'drawdown']]

        if not drawdowns.empty:
            for _, row in drawdowns.sort_values('drawdown').head(5).iterrows():
                drawdown_data.append({
                    "startDate": row['date'].strftime('%Y-%m-%d'),
                    "endDate": row['date'].strftime('%Y-%m-%d'),
                    "value": round(row['drawdown'] * 100, 2)  # 转成百分比
                })

        # 4. 月度收益热力图
        heatmap_data = []
        try:
            df_equity = df[['date', 'total_value']].copy()
            df_equity = df_equity.set_index('date')
            df_equity['year'] = df_equity.index.year
            df_equity['month'] = df_equity.index.month

            monthly_returns = []
            for (year, month), group in df_equity.groupby(['year', 'month']):
                first_value = group['total_value'].iloc[0]
                last_value = group['total_value'].iloc[-1]
                if first_value <= 0:
                    continue
                monthly_returns.append({
                    'year': int(year),
                    'month': int(month),
                    'return': (last_value / first_value - 1)
                })

            monthly_returns_df = pd.DataFrame(monthly_returns)
            if not monthly_returns_df.empty:
                monthly_returns_df = monthly_returns_df.sort_values(['year', 'month'])
                for year, group in monthly_returns_df.groupby('year'):
                    year_data = {
                        'year': int(year),
                        'months': [None] * 12   # 1~12 月
                    }
                    for _, row in group.iterrows():
                        m = int(row['month']) - 1
                        year_data['months'][m] = round(row['return'] * 100, 2)  # 百分比
                    heatmap_data.append(year_data)

        except Exception as e:
            print(f"计算月度收益失败: {e}")

        return {
            "drawdowns": drawdown_data,
            "volatility": [],          # 你后面如果想补充波动率 / 分布可以用这两个
            "returnDistribution": [],
            "monthlyReturns": heatmap_data
        }
    def stream_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        benchmark_code: Optional[str] = None,
        stop_event: Optional[Event] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        CHANGED: 流式 API 层（支持懒加载初始化）
        
        1. 首次调用时初始化数据库连接
        2. 发送初始化状态事件给前端
        3. 调用流式引擎
        4. 包装引擎数据，添加基准和实时指标
        """
        # CHANGED: 确保数据库已初始化（懒加载）
        if not self._initialized:
            # 发送初始化开始事件
            yield {
                "type": "initializing",
                "data": {
                    "message": "正在初始化数据库连接...",
                    "progress": 0
                }
            }
            
            try:
                self._ensure_initialized()
                # 发送初始化完成事件
                yield {
                    "type": "initialized",
                    "data": {
                        "message": "数据库连接初始化完成",
                        "progress": 100
                    }
                }
            except Exception as e:
                # 发送初始化失败事件
                yield {
                    "type": "error",
                    "data": {
                        "message": f"数据库连接初始化失败: {e}"
                    }
                }
                return
        
        initial_capital = self.backtest_engine.initial_capital
        
        # 1. (准备基准数据 - 这仍然是一次性加载)
        dates = self.data_query.get_trading_dates(start_date, end_date)
        benchmark_curve = []
        if benchmark_code:
            benchmark_df = self._get_benchmark_data_from_db(benchmark_code, start_date, end_date)
        else:
            benchmark_df = pd.DataFrame() 

        if benchmark_code and not benchmark_df.empty:
            try:
                strategy_dates_df = pd.DataFrame({'date': dates})
                merged_df = pd.merge(strategy_dates_df, benchmark_df, on='date', how='left')
                merged_df['close'] = merged_df['close'].ffill().bfill()
                first_valid_benchmark = merged_df['close'].dropna().iloc[0]
                if first_valid_benchmark > 0:
                    normalized_curve = (merged_df['close'] / first_valid_benchmark) * initial_capital
                    benchmark_curve = normalized_curve.fillna(initial_capital).tolist()
                else:
                    benchmark_curve = [initial_capital] * len(dates)
            except Exception as e:
                print(f"标准化基准时出错: {e}")
                benchmark_curve = [initial_capital] * len(dates)
        
        if not benchmark_curve:
            benchmark_curve = [initial_capital] * len(dates)
            
        # (将基准数据转换为 日期 -> 值 的映射，以便快速查找)
        benchmark_map = dict(zip(dates, benchmark_curve))

        # (用于计算实时回撤)
        cummax_equity = initial_capital
        
        # 收集权益曲线，用于最后计算风险指标
        equity_records = []
        
        try:
            # 调用流式引擎
            creation_kwargs: Dict[str, Any] = params or {}
            strategy = StrategyFactory.create_strategy(strategy_name, use_simple=True, **creation_kwargs)
            engine_generator = self.backtest_engine.run_backtest_streaming(
                start_date, end_date, strategy, stop_event=stop_event
            )

            # 3. 循环遍历引擎的【产出】
            for update in engine_generator:
                if stop_event and stop_event.is_set():
                    yield {
                        "type": "cancelled",
                        "data": {"message": "回测已取消"}
                    }
                    break
                
                # A. 如果是交易或错误，直接转发
                if update['type'] == 'new_trade_engine':
                    
                    trade_data = update['data']
                    symbol_code = self._normalize_symbol_code(trade_data.get('symbol') or trade_data.get('symbol_code'))
                    if not symbol_code:
                        continue
                    position_id = trade_data.get('position_id') or f"{symbol_code}_{trade_data['date']}"
                    symbol_name = self.stock_info_map.get(symbol_code, symbol_code)

                    # 简化：直接转发引擎数据，引擎已提供所有必要信息
                    yield {
                        "type": "new_trade",
                        "data": {
                            "id": f"trade-{trade_data['date']}-{symbol_code}",
                            "date": trade_data['date'],
                            "symbol": symbol_name,
                            "symbolCode": symbol_code,
                            "symbol_code": symbol_code,
                            "action": trade_data['action'],
                            "price": trade_data['price'],
                            "quantity": trade_data['quantity'],
                            "profitLoss": trade_data.get('profit_loss', 0),
                            "cumulativePnL": trade_data.get('cumulative_pnl', 0),
                            "positionId": position_id,
                            "entryDate": trade_data.get('entry_date'),
                            "exitDate": trade_data.get('exit_date'),
                            # CHANGED: 添加 FIFO 匹配的结果
                            "entry_price": trade_data.get('entry_price'),
                            "exit_price": trade_data.get('exit_price'),
                            "profit_loss": trade_data.get('profit_loss'),
                            "roi": trade_data.get('roi'),
                            "holding_days": trade_data.get('holding_days')
                        }
                    }
                elif update['type'] in ['error', 'backtest_start', 'final_metrics', 'stream_complete', 'progress']:
                    if update['type'] == 'stream_complete':
                        # 回测结束，计算最终风险指标
                        if equity_records:
                            try:
                                results_df = pd.DataFrame(equity_records)
                                risk_data = self._calculate_risk_from_df(results_df)
                                yield {
                                    "type": "risk_data",
                                    "data": risk_data
                                }
                            except Exception as e:
                                print(f"计算风险数据失败: {e}")
                        yield update
                        return
                    else:
                        yield update
                elif update['type'] == 'daily_equity_engine':
                    engine_data = update['data']
                    current_date = engine_data['date']
                    equity = engine_data['strategyReturn']
                    
                    
                    # (计算实时指标)
                    current_total_return = (equity / initial_capital - 1) * 100
                    if equity > cummax_equity:
                        cummax_equity = equity
                    current_drawdown = ((equity - cummax_equity) / cummax_equity) * 100
                    
                    # (添加基准)
                    benchmark_val = benchmark_map.get(current_date, initial_capital)
                    
                    # 收集权益数据用于后续计算风险指标
                    equity_records.append({
                        'date': current_date,
                        'total_value': equity
                    })
                    
                    # (打包成前端需要的 'daily_update' 格式)
                    yield {
                        "type": "daily_equity", # (这是 app.py 认识的名字)
                        "data": {
                            "date": current_date,
                            "strategyReturn": equity,
                            "benchmarkReturn": benchmark_val,
                            "totalReturn": current_total_return, 
                            "currentDrawdown": current_drawdown  
                        }
                    }

                if stop_event and stop_event.is_set():
                    yield {
                        "type": "cancelled",
                        "data": {"message": "回测已取消"}
                    }
                    break

        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": str(e)}
            }
