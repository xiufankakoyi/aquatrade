"""
回测服务
负责回测执行和结果处理
"""
from typing import Dict, List, Any, Optional, Generator, Tuple
from datetime import datetime
from threading import Event
import pandas as pd
import numpy as np
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine
from core.strategies.strategy_factory import StrategyFactory
from server.services.data_initialization_service import DataInitializationService
from server.services.metrics_service import MetricsService
from server.services.stock_data_service import StockDataService
from server.utils.symbol_utils import normalize_symbol_code
from config.logger import get_logger

logger = get_logger(__name__)


class BacktestService:
    """回测服务类"""
    
    def __init__(self, init_service: DataInitializationService, metrics_service: MetricsService, stock_data_service: StockDataService):
        self.init_service = init_service
        self.metrics_service = metrics_service
        self.stock_data_service = stock_data_service
    
    @property
    def stock_info_map(self) -> Dict[str, str]:
        """获取股票信息映射"""
        if self.init_service.stock_info_map:
            return self.init_service.stock_info_map
        
        try:
            from data_svc.unified_data_query import get_stock_basic
            df = get_stock_basic()
            if df is not None and not df.empty:
                result = {}
                for _, row in df.iterrows():
                    code = str(row.get('code', '')).strip()
                    name = str(row.get('name', '')).strip()
                    if code and name:
                        code_6 = code.zfill(6) if len(code) <= 6 else code[-6:]
                        result[code_6] = name
                return result
        except Exception as e:
            logger.warning(f"从 ArcticDB 获取股票信息失败: {e}")
        
        return {}
    
    def _prepare_benchmark_data(
        self, 
        benchmark_code: Optional[str], 
        start_date: str, 
        end_date: str,
        dates: List[str],
        initial_capital: float
    ) -> Tuple[List[float], Dict[str, float]]:
        """
        准备基准数据
        
        Args:
            benchmark_code: 基准代码
            start_date: 开始日期
            end_date: 结束日期
            dates: 交易日列表
            initial_capital: 初始资金
        
        Returns:
            Tuple[benchmark_curve, benchmark_map]: 基准曲线和日期映射
        """
        if not benchmark_code:
            benchmark_curve = [initial_capital] * len(dates)
            return benchmark_curve, dict(zip(dates, benchmark_curve))
        
        benchmark_df = self.stock_data_service.get_benchmark_data_from_db(benchmark_code, start_date, end_date)
        
        if benchmark_df.empty:
            benchmark_curve = [initial_capital] * len(dates)
            return benchmark_curve, dict(zip(dates, benchmark_curve))
        
        try:
            strategy_dates_df = pd.DataFrame({'date': dates})
            merged_df = pd.merge(strategy_dates_df, benchmark_df, on='date', how='left')
            merged_df['close'] = merged_df['close'].ffill().bfill()
            first_valid = merged_df['close'].dropna().iloc[0]
            
            if first_valid > 0:
                normalized_curve = (merged_df['close'] / first_valid) * initial_capital
                benchmark_curve = normalized_curve.fillna(initial_capital).tolist()
            else:
                benchmark_curve = [initial_capital] * len(dates)
        except Exception as e:
            logger.warning(f"标准化基准数据失败: {e}")
            benchmark_curve = [initial_capital] * len(dates)
        
        return benchmark_curve, dict(zip(dates, benchmark_curve))
    
    def _calculate_benchmark_metrics(
        self, 
        benchmark_records: List[Dict], 
        initial_capital: float
    ) -> Tuple[float, float]:
        """
        计算基准指标
        
        Args:
            benchmark_records: 基准记录列表
            initial_capital: 初始资金
        
        Returns:
            Tuple[benchmark_return, benchmark_volatility]: 基准收益率和波动率
        """
        if not benchmark_records:
            return 0.0, 0.0
        
        try:
            benchmark_df = pd.DataFrame(benchmark_records)
            values = benchmark_df['total_value'].values
            
            if len(values) == 0:
                return 0.0, 0.0
            
            benchmark_return = (values[-1] / initial_capital - 1) * 100
            
            if len(values) > 1:
                series = pd.Series(values)
                returns = series.pct_change().dropna()
                benchmark_volatility = returns.std() * np.sqrt(252) * 100 if not returns.empty else 0.0
            else:
                benchmark_volatility = 0.0
            
            return benchmark_return, benchmark_volatility
        except Exception as e:
            logger.warning(f"计算基准指标失败: {e}")
            return 0.0, 0.0
    
    def _calculate_monthly_returns(self, equity_records: List[Dict]) -> List[Dict]:
        """
        计算月度收益
        
        Args:
            equity_records: 权益记录列表
        
        Returns:
            月度收益列表，格式：[{year: number, months: (number | null)[]}]
        """
        if not equity_records:
            return []
        
        try:
            df = pd.DataFrame(equity_records)
            df['date'] = pd.to_datetime(df['date'])
            df['year'] = df['date'].dt.year
            df['month'] = df['date'].dt.month
            
            monthly_returns = []
            for year, year_group in df.groupby('year'):
                year_data = {
                    'year': int(year),
                    'months': [None] * 12
                }
                
                for month, month_group in year_group.groupby('month'):
                    first_equity = month_group['total_value'].iloc[0]
                    last_equity = month_group['total_value'].iloc[-1]
                    if first_equity > 0:
                        monthly_return = (last_equity - first_equity) / first_equity * 100
                        year_data['months'][int(month) - 1] = float(round(monthly_return, 2))
                
                monthly_returns.append(year_data)
            
            return monthly_returns
        except Exception as e:
            logger.warning(f"计算月度收益失败: {e}")
            return []
    
    def _get_stock_name(self, symbol_code: str) -> str:
        """获取股票名称，优先从缓存获取"""
        symbol_name = self.stock_info_map.get(symbol_code)
        if symbol_name and symbol_name != symbol_code:
            return symbol_name
        
        try:
            from data_svc.unified_data_query import get_unified_data_adapter
            adapter = get_unified_data_adapter()
            name_map = adapter.get_stock_names([symbol_code])
            return name_map.get(symbol_code, symbol_code)
        except Exception:
            return symbol_code
    
    def run_backtest_and_get_data(self, strategy_name: str, start_date: str, end_date: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """
        运行回测并获取数据（流式回测并收集结果）
        """
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()

        local_data_query = OptimizedStockDataQuery(warmup=True)
        
        try:
            creation_kwargs: Dict[str, Any] = params or {}
            strategy = StrategyFactory.create_strategy(strategy_name, use_simple=True, **creation_kwargs)
            
            # 从策略读取配置，创建引擎配置
            from core.backtest.unified_engine import BacktestConfig
            engine_config = BacktestConfig()
            
            # 读取策略的仓位配置
            if hasattr(strategy, 'position_ratio'):
                engine_config.position_ratio = strategy.position_ratio
            if hasattr(strategy, 'max_positions'):
                engine_config.max_positions = strategy.max_positions
            if hasattr(strategy, 'max_stocks_per_day'):
                engine_config.max_stocks_per_day = strategy.max_stocks_per_day
            
            # 读取策略的止损止盈配置
            if hasattr(strategy, 'config'):
                strategy_config = strategy.config
                if hasattr(strategy_config, 'stop_loss_pct'):
                    engine_config.stop_loss = strategy_config.stop_loss_pct
                if hasattr(strategy_config, 'take_profit_pct'):
                    engine_config.take_profit = strategy_config.take_profit_pct
                if hasattr(strategy_config, 'max_hold_days'):
                    engine_config.max_holding_days = strategy_config.max_hold_days
            
            local_engine = UnifiedBacktestEngine(local_data_query, engine_config)
            
            results_list = []
            trades_log = []
            final_metrics = None
            
            for update in local_engine.run_backtest_streaming(start_date, end_date, strategy):
                update_type = update.get('type')
                data = update.get('data', {})
            
                if update_type == 'daily_equity_engine':
                    results_list.append({
                        'date': data.get('date'),
                        'total_value': data.get('strategyReturn', 0)
                    })
                elif update_type in ('new_trade', 'new_trade_engine'):
                    trade = {
                        'date': data.get('date'),
                        'symbol': data.get('symbol') or data.get('symbol_code', ''),
                        'action': data.get('action'),
                        'price': data.get('price', 0),
                        'quantity': data.get('quantity', 0),
                        'commission': data.get('commission', 0),
                        'entry_date': data.get('entry_date'),
                        'exit_date': data.get('exit_date'),
                        'position_id': data.get('position_id'),
                        'profit_loss': data.get('profit_loss', 0),
                        'roi': data.get('roi'),
                        'holding_days': data.get('holding_days')
                    }
                    trades_log.append(trade)
                elif update_type == 'final_metrics':
                    final_metrics = data
                elif update_type == 'error':
                    return {"error": data.get('message', '回测发生错误')}
            
            if not results_list:
                return {
                    "error": f"回测没有产生任何结果。请检查数据库 '{self.init_service.db_path}' 中 "
                             f"是否存在 {start_date} 到 {end_date} 期间的股票数据。"
                }
            
            results_df = pd.DataFrame(results_list)
            results_df['date'] = pd.to_datetime(results_df['date'])
            results_df = results_df.sort_values('date')
            
            return self.convert_backtest_results(results_df, trades_log, strategy_name, start_date, end_date)
        except Exception as e:
            logger.error(f"运行回测错误: {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            try:
                local_data_query.close()
            except Exception:
                pass
    
    def convert_backtest_results(self, results_df: pd.DataFrame, trades_log: List[Dict], 
                                 strategy_name: str, start_date: str, end_date: str) -> Dict:
        """转换回测结果为前端格式"""
        metrics = self.metrics_service.calculate_metrics_from_df(results_df, trades_log)
        equity_curve = self.metrics_service.extract_equity_curve_from_df(results_df, self.stock_data_service)
        risk_data = self.metrics_service.calculate_risk_from_df(results_df)
        
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
        for trade in trades_log:
             raw_symbol_code = normalize_symbol_code(trade.get('symbol') or trade.get('symbol_code', ''))
             entry_date = trade.get('entry_date')
             exit_date = trade.get('exit_date')
             
             holding_days = None
             if entry_date and exit_date:
                 try:
                     entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                     exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
                     holding_days = (exit_dt - entry_dt).days
                 except:
                     pass
             elif entry_date and trade['action'] == 'sell':
                 try:
                     entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                     trade_dt = datetime.strptime(trade['date'], '%Y-%m-%d')
                     holding_days = (trade_dt - entry_dt).days
                 except:
                     pass
             
             commission_base = trade.get('commission', trade['price'] * trade['quantity'] * 0.0005)
             commission = max(commission_base, 5.0) if commission_base > 0 else 5.0
             
             entry_price = trade.get('entry_price')
             exit_price = trade.get('exit_price')
             profit_loss = trade.get('profit_loss')
             roi = trade.get('roi')
             holding_days_from_engine = trade.get('holding_days')
             
             if holding_days_from_engine is not None:
                 holding_days = holding_days_from_engine
             
             formatted_trades.append({
                "id": f"trade-{trade['date']}-{raw_symbol_code}-{trade['action']}",
                "date": trade['date'],
                "symbol": self.stock_info_map.get(raw_symbol_code, raw_symbol_code),
                "symbolCode": raw_symbol_code,
                "symbol_code": raw_symbol_code,
                "action": trade['action'],
                "price": trade['price'],
                "quantity": trade['quantity'],
                "value": trade.get('price', 0) * trade.get('quantity', 0),
                "commission": commission,
                "profitLoss": profit_loss if profit_loss is not None else trade.get('profitLoss', 0),
                "cumulativePnL": trade.get('cumulativePnL', 0),
                "entryDate": entry_date,
                "exitDate": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "profit_loss": profit_loss,
                "roi": roi,
                "positionId": trade.get('position_id'),
                "holdingDays": holding_days
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
    
    def stream_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        benchmark_code: Optional[str] = None,
        stop_event: Optional[Event] = None,
        params: Optional[Dict[str, Any]] = None,
        backtest_config: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        流式回测 API
        
        1. 懒加载初始化数据库连接
        2. 调用流式引擎
        3. 包装引擎数据，添加基准和实时指标
        """
        if not self.init_service._initialized:
            yield {"type": "initializing", "data": {"message": "正在初始化数据库连接...", "progress": 0}}
            try:
                self.init_service.ensure_initialized()
                yield {"type": "initialized", "data": {"message": "数据库连接初始化完成", "progress": 100}}
            except Exception as e:
                yield {"type": "error", "data": {"message": f"数据库连接初始化失败: {e}"}}
                return
        
        engine = self.init_service.backtest_engine
        if backtest_config:
            if backtest_config.get('initial_capital') is not None:
                engine.initial_capital = backtest_config['initial_capital']
                logger.info(f"设置初始资金: {backtest_config['initial_capital']}")
            if backtest_config.get('commission') is not None:
                engine.commission_rate = backtest_config['commission']
                logger.info(f"设置佣金率: {backtest_config['commission']}")
            if backtest_config.get('slippage') is not None:
                if hasattr(engine, 'slippage'):
                    engine.slippage = backtest_config['slippage']
                    logger.info(f"设置滑点: {backtest_config['slippage']}")
                else:
                    logger.warning("引擎不支持滑点设置")
        
        initial_capital = engine.initial_capital
        dates = self.init_service.data_query.get_trading_dates(start_date, end_date)
        benchmark_curve, benchmark_map = self._prepare_benchmark_data(
            benchmark_code, start_date, end_date, dates, initial_capital
        )
        
        cummax_equity = initial_capital
        equity_records = []
        benchmark_records = []
        
        try:
            creation_kwargs: Dict[str, Any] = params or {}
            strategy = StrategyFactory.create_strategy(strategy_name, use_simple=True, **creation_kwargs)
            
            engine_generator = self.init_service.backtest_engine.run_backtest_streaming(
                start_date, end_date, strategy, stop_event=stop_event
            )

            for update in engine_generator:
                if stop_event and stop_event.is_set():
                    yield {"type": "cancelled", "data": {"message": "回测已取消"}}
                    break
                
                update_type = update['type']
                
                if update_type == 'new_trade_engine':
                    yield from self._process_trade_event(update['data'])
                    
                elif update_type == 'stream_complete':
                    yield from self._process_stream_complete(
                        update, equity_records, benchmark_records, initial_capital
                    )
                    return
                    
                elif update_type in ('initializing', 'initialized', 'backtest_start', 'daily_update', 
                                     'order_update', 'backtest_end', 'error', 'final_metrics', 'progress'):
                    yield update
                    
                elif update_type == 'daily_equity_engine':
                    yield from self._process_daily_equity(
                        update['data'], benchmark_map, initial_capital, 
                        cummax_equity, equity_records, benchmark_records
                    )
                    cummax_equity = max(cummax_equity, update['data'].get('strategyReturn', initial_capital))

                if stop_event and stop_event.is_set():
                    yield {"type": "cancelled", "data": {"message": "回测已取消"}}
                    break

        except Exception as e:
            yield {"type": "error", "data": {"message": str(e)}}
    
    def _process_trade_event(self, trade_data: Dict) -> Generator[Dict[str, Any], None, None]:
        """处理交易事件"""
        symbol_code = normalize_symbol_code(trade_data.get('symbol') or trade_data.get('symbol_code'))
        if not symbol_code:
            return
        
        position_id = trade_data.get('position_id') or f"{symbol_code}_{trade_data['date']}"
        symbol_name = self._get_stock_name(symbol_code)
        
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
                "entry_price": trade_data.get('entry_price'),
                "exit_price": trade_data.get('exit_price'),
                "profit_loss": trade_data.get('profit_loss'),
                "roi": trade_data.get('roi'),
                "holding_days": trade_data.get('holding_days')
            }
        }
    
    def _process_daily_equity(
        self, 
        engine_data: Dict, 
        benchmark_map: Dict[str, float],
        initial_capital: float,
        cummax_equity: float,
        equity_records: List[Dict],
        benchmark_records: List[Dict]
    ) -> Generator[Dict[str, Any], None, None]:
        """处理每日权益事件"""
        current_date = engine_data['date']
        equity = engine_data['strategyReturn']
        
        current_total_return = (equity / initial_capital - 1) * 100
        if equity > cummax_equity:
            cummax_equity = equity
        current_drawdown = ((equity - cummax_equity) / cummax_equity) * 100
        
        benchmark_val = benchmark_map.get(current_date, initial_capital)
        
        equity_records.append({'date': current_date, 'total_value': equity})
        benchmark_records.append({'date': current_date, 'total_value': benchmark_val})
        
        yield {
            "type": "daily_equity",
            "data": {
                "date": current_date,
                "strategyReturn": equity,
                "benchmarkReturn": benchmark_val,
                "totalReturn": current_total_return,
                "currentDrawdown": current_drawdown
            }
        }
    
    def _process_stream_complete(
        self,
        update: Dict,
        equity_records: List[Dict],
        benchmark_records: List[Dict],
        initial_capital: float
    ) -> Generator[Dict[str, Any], None, None]:
        """处理回测完成事件"""
        if equity_records:
            try:
                results_df = pd.DataFrame(equity_records)
                risk_data = self.metrics_service.calculate_risk_from_df(results_df)
                yield {"type": "risk_data", "data": risk_data}
            except Exception as e:
                logger.warning(f"计算风险数据失败: {e}")
        
        benchmark_return, benchmark_volatility = self._calculate_benchmark_metrics(
            benchmark_records, initial_capital
        )
        
        strategy_return = update['data'].get('totalReturn', 0)
        excess_return = strategy_return - benchmark_return
        
        engine_data = update['data']
        engine_data['benchmarkReturn'] = round(benchmark_return, 2)
        engine_data['excessReturn'] = round(excess_return, 2)
        engine_data['benchmarkVolatility'] = round(benchmark_volatility, 2)
        
        if not engine_data.get('equityCurve') and equity_records:
            engine_data['equityCurve'] = [
                {"date": r['date'], "equity": round(r['total_value'], 2)}
                for r in equity_records
            ]
        
        if benchmark_records:
            engine_data['benchmarkCurve'] = [
                {"date": r['date'], "equity": round(r['total_value'], 2)}
                for r in benchmark_records
            ]
        
        if not engine_data.get('monthlyReturns') and equity_records:
            engine_data['monthlyReturns'] = self._calculate_monthly_returns(equity_records)
        
        yield update

