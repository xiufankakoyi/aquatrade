"""
回测服务
负责回测执行和结果处理
"""
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime
from threading import Event
import pandas as pd
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.optimized_backtest_engine import OptimizedBacktestEngine
from core.strategies.strategy_factory import StrategyFactory
from server.services.data_initialization_service import DataInitializationService
from server.services.metrics_service import MetricsService
from server.services.stock_data_service import StockDataService
from server.utils.symbol_utils import normalize_symbol_code


class BacktestService:
    """回测服务类"""
    
    def __init__(self, init_service: DataInitializationService, metrics_service: MetricsService, stock_data_service: StockDataService):
        self.init_service = init_service
        self.metrics_service = metrics_service
        self.stock_data_service = stock_data_service
    
    @property
    def stock_info_map(self) -> Dict[str, str]:
        """获取股票信息映射"""
        return self.init_service.stock_info_map
    
    def run_backtest_and_get_data(self, strategy_name: str, start_date: str, end_date: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """
        运行回测并获取数据（真实数据，作为备用）
        CHANGED: 使用流式回测并收集结果
        """
        if not self.init_service._initialized:
            self.init_service.ensure_initialized()

        # 为每次回测创建独立的数据查询和回测引擎，避免并发共享同一个 DuckDB 连接导致异常
        local_data_query = OptimizedStockDataQuery(self.init_service.db_path)
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
                elif update_type == 'new_trade' or update_type == 'new_trade_engine':
                    # CHANGED: 监听正确的事件类型，同时兼容两种事件名
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
                        'position_id': data.get('position_id'),
                        'profit_loss': data.get('profit_loss', 0),
                        'roi': data.get('roi'),
                        'holding_days': data.get('holding_days')
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
                    f"请检查数据库 '{self.init_service.db_path}' 中 "
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
                metrics = self.metrics_service.calculate_metrics_from_df(results_df, trades_log)
            
            # 调用转换函数
            return self.convert_backtest_results(
                results_df, trades_log, strategy_name, start_date, end_date
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
    
    def convert_backtest_results(self, results_df: pd.DataFrame, trades_log: List[Dict], 
                                 strategy_name: str, start_date: str, end_date: str) -> Dict:
        """
        (此函数保持不变, 作为备用)
        转换回测结果
        """
        
        metrics = self.metrics_service.calculate_metrics_from_df(results_df, trades_log)
        equity_curve = self.metrics_service.extract_equity_curve_from_df(results_df, self.stock_data_service)
        risk_data = self.metrics_service.calculate_risk_from_df(results_df)
        
        # (格式化交易记录)
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
             raw_symbol_code = normalize_symbol_code(trade.get('symbol') or trade.get('symbol_code', ''))
             entry_date = trade.get('entry_date')
             exit_date = trade.get('exit_date')
             
             # CHANGED: 计算持有周期（天数）
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
        if not self.init_service._initialized:
            # 发送初始化开始事件
            yield {
                "type": "initializing",
                "data": {
                    "message": "正在初始化数据库连接...",
                    "progress": 0
                }
            }
            
            try:
                self.init_service.ensure_initialized()
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
        
        initial_capital = self.init_service.backtest_engine.initial_capital
        
        # 1. (准备基准数据 - 这仍然是一次性加载)
        import time
        dates = self.init_service.data_query.get_trading_dates(start_date, end_date)
        
        benchmark_curve = []
        if benchmark_code:
            benchmark_df = self.stock_data_service.get_benchmark_data_from_db(benchmark_code, start_date, end_date)
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
            
            engine_generator = self.init_service.backtest_engine.run_backtest_streaming(
                start_date, end_date, strategy, stop_event=stop_event
            )

            # 3. 循环遍历引擎的【产出】
            update_count = 0
            for update in engine_generator:
                update_count += 1
                if stop_event and stop_event.is_set():
                    yield {
                        "type": "cancelled",
                        "data": {"message": "回测已取消"}
                    }
                    break
                
                # A. 如果是交易或错误，直接转发
                if update['type'] == 'new_trade_engine':
                    
                    trade_data = update['data']
                    symbol_code = normalize_symbol_code(trade_data.get('symbol') or trade_data.get('symbol_code'))
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
                # 修改后: 添加 initializing 和 initialized
                elif update['type'] in [
                    'initializing',   # 新增: 通知前端开始加载数据
                    'initialized',    # 新增: 通知前端数据加载完成
                    'backtest_start', 
                    'daily_update', 
                    'order_update', 
                    'backtest_end',
                    'error',           # 建议: 确保错误事件也能透传
                    'final_metrics',
                    'stream_complete',
                    'progress'
                ]:
                    if update['type'] == 'stream_complete':
                        # 回测结束，计算最终风险指标
                        if equity_records:
                            try:
                                results_df = pd.DataFrame(equity_records)
                                risk_data = self.metrics_service.calculate_risk_from_df(results_df)
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

