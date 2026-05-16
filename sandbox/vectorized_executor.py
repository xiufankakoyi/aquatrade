"""
向量化交易执行引擎
=================
使用 Polars 向量化操作替代 Python 循环，大幅提升交易执行性能。

核心优化:
1. 批量信号处理 - 一次性处理所有买卖信号
2. 向量化价格查询 - 避免逐个股票查询
3. 向量化盈亏计算 - 使用 Polars 表达式计算
4. 批量交易记录生成 - 一次性生成所有交易记录

使用方法:
    from sandbox.vectorized_executor import VectorizedExecutionEngine
    
    executor = VectorizedExecutionEngine(
        commission_rate=0.0003,
        min_commission=5.0,
        sell_tax=0.001
    )
    
    portfolio, cash, trades = executor.execute_trades(
        current_time=pd.Timestamp('2024-01-15'),
        stock_pool_pl=stock_pool_df,  # Polars DataFrame
        signals={'000001.SZ': 'buy', '000002.SZ': 'sell'},
        current_portfolio={'000001.SZ': 1000},
        current_cash=1000000.0
    )
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import time

import pandas as pd
import polars as pl
import numpy as np


class VectorizedExecutionEngine:
    """
    向量化交易执行引擎
    
    使用 Polars 的向量化操作替代传统的 Python 循环，
    在处理大量交易信号时可获得 10-50 倍性能提升。
    """
    
    def __init__(
        self,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        sell_tax: float = 0.001
    ):
        """
        初始化执行引擎
        
        Args:
            commission_rate: 手续费率 (默认 0.03%)
            min_commission: 最小手续费 (默认 5元)
            sell_tax: 卖出印花税 (默认 0.1%)
        """
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.sell_tax = sell_tax
        
        # 性能统计
        self._perf_stats = {
            'total_calls': 0,
            'total_duration': 0.0,
            'total_trades': 0
        }
    
    def execute_trades(
        self,
        current_time: pd.Timestamp,
        stock_pool_pl: pl.DataFrame,
        signals: Dict[str, Any],
        current_portfolio: Dict[str, int],
        current_cash: float,
        position_info: Optional[Dict[str, Dict[str, Any]]] = None,
        strategy: Any = None
    ) -> Tuple[Dict[str, int], float, List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        【核心方法】向量化执行交易
        
        一次性处理所有信号，使用 Polars 向量化操作。
        
        Args:
            current_time: 当前时间
            stock_pool_pl: 当日股票池 (Polars DataFrame)
            signals: 交易信号 {stock_code: signal}
            current_portfolio: 当前持仓 {stock_code: shares}
            current_cash: 当前现金
            position_info: 持仓成本信息 {stock_code: {'cost': float, 'entry_date': str}}
            strategy: 策略对象，用于获取 position_ratio 和 max_positions
        
        Returns:
            (new_portfolio, new_cash, trades_list, new_position_info)
        """
        # 【对齐传统执行】从策略获取仓位配置
        self._strategy_position_ratio = getattr(strategy, 'position_ratio', None)
        self._strategy_max_positions = getattr(strategy, 'max_positions', None)
        
        # 【价格策略修复】从策略获取执行价格类型
        self._buy_price_type = 'close'  # 默认使用收盘价
        self._sell_price_type = 'close'
        if strategy is not None and hasattr(strategy, 'get_execution_price'):
            self._buy_price_type = strategy.get_execution_price('buy')
            self._sell_price_type = strategy.get_execution_price('sell')
        
        start_time = time.time()
        
        # 初始化
        new_portfolio = current_portfolio.copy()
        new_cash = current_cash
        new_position_info = (position_info or {}).copy()
        date_str = current_time.strftime('%Y-%m-%d')
        
        if not signals or stock_pool_pl.is_empty():
            return new_portfolio, new_cash, [], new_position_info
        
        # 1. 将信号转换为 Polars DataFrame
        signals_df = self._signals_to_dataframe(signals)
        
        # 2. 与股票池 Join - 向量化获取价格数据
        trade_data = self._prepare_trade_data(stock_pool_pl, signals_df)
        
        if trade_data.is_empty():
            return new_portfolio, new_cash, [], new_position_info
        
        # 3. 分离买卖信号
        sells = trade_data.filter(pl.col('action').is_in(['sell', 'exit']))
        buys = trade_data.filter(pl.col('action').is_in(['buy', 'enter']))
        
        # 4. 向量化执行卖出
        sell_results = self._execute_sells_vectorized(
            sells=sells,
            portfolio=new_portfolio,
            cash=new_cash,
            position_info=new_position_info,
            date_str=date_str
        )
        
        new_portfolio = sell_results['portfolio']
        new_cash = sell_results['cash']
        new_position_info = sell_results['position_info']
        sell_trades = sell_results['trades']
        
        # 5. 向量化执行买入 (使用更新后的现金)
        # 【对齐传统执行】传入策略的仓位配置
        buy_results = self._execute_buys_vectorized(
            buys=buys,
            portfolio=new_portfolio,
            cash=new_cash,
            date_str=date_str,
            max_positions=self._strategy_max_positions,
            position_ratio=self._strategy_position_ratio
        )
        
        new_portfolio = buy_results['portfolio']
        new_cash = buy_results['cash']
        new_position_info = buy_results['position_info']
        buy_trades = buy_results['trades']
        
        # 6. 合并交易记录
        all_trades = sell_trades + buy_trades
        
        # 更新性能统计
        duration = time.time() - start_time
        self._perf_stats['total_calls'] += 1
        self._perf_stats['total_duration'] += duration
        self._perf_stats['total_trades'] += len(all_trades)
        
        return new_portfolio, new_cash, all_trades, new_position_info
    
    def _signals_to_dataframe(self, signals: Dict[str, Any]) -> pl.DataFrame:
        """
        将信号字典转换为 Polars DataFrame
        
        支持多种信号格式:
        - 简单格式: {'000001.SZ': 'buy'}
        - 字典格式: {'000001.SZ': {'action': 'buy', 'weight': 0.5}}
        """
        records = []
        for code, signal in signals.items():
            if isinstance(signal, dict):
                action = signal.get('action', 'hold')
                weight = signal.get('weight', 1.0)
                indicators = signal.get('indicators', {})
            else:
                action = str(signal)
                weight = 1.0
                indicators = {}
            
            records.append({
                'stock_code': code,
                'action': action,
                'weight': weight,
                'indicators': indicators
            })
        
        return pl.DataFrame(records)
    
    def _prepare_trade_data(
        self,
        stock_pool_pl: pl.DataFrame,
        signals_df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        准备交易数据 - Join 信号和股票池
        
        返回包含完整交易信息的 DataFrame
        """
        # 确保股票池有必要列
        required_cols = ['stock_code', 'open', 'close']
        available_cols = [c for c in required_cols if c in stock_pool_pl.columns]
        
        if not available_cols:
            return pl.DataFrame()
        
        # 选择需要的列
        pool_cols = ['stock_code', 'open', 'close', 'high', 'low', 'volume', 
                     'is_suspended', 'is_limit_up', 'is_limit_down', 'adj_factor']
        pool_cols = [c for c in pool_cols if c in stock_pool_pl.columns]
        
        pool_subset = stock_pool_pl.select(pool_cols)
        
        # Join 信号和股票池
        trade_data = signals_df.join(
            pool_subset,
            left_on='stock_code',
            right_on='stock_code',
            how='inner'
        )
        
        return trade_data
    
    def _execute_sells_vectorized(
        self,
        sells: pl.DataFrame,
        portfolio: Dict[str, int],
        cash: float,
        position_info: Dict[str, Dict[str, Any]],
        date_str: str
    ) -> Dict[str, Any]:
        """
        向量化执行卖出操作
        
        一次性计算所有卖出的金额、手续费、盈亏
        """
        trades = []
        
        if sells.is_empty():
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': position_info,
                'trades': trades
            }
        
        # 过滤有持仓的股票
        portfolio_codes = set(portfolio.keys())
        
        # 添加持仓数量列
        sells = sells.with_columns([
            pl.col('stock_code').map_elements(
                lambda x: portfolio.get(x, 0),
                return_dtype=pl.Int64
            ).alias('shares_held')
        ])
        
        # 过滤有效卖出
        # 构建过滤条件
        filter_conditions = [
            pl.col('shares_held') > 0,
            pl.col(self._sell_price_type) > 0,
        ]
        
        # 动态添加过滤条件（如果列存在）
        if 'is_suspended' in sells.columns:
            filter_conditions.append(~pl.col('is_suspended').fill_null(False))
        if 'is_limit_down' in sells.columns:
            filter_conditions.append(~pl.col('is_limit_down').fill_null(False))
        
        valid_sells = sells.filter(pl.all_horizontal(filter_conditions))
        
        if valid_sells.is_empty():
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': position_info,
                'trades': trades
            }
        
        # 向量化计算卖出金额和费用
        valid_sells = valid_sells.with_columns([
            # 卖出收入
            (pl.col('shares_held') * pl.col(self._sell_price_type)).alias('revenue'),
        ]).with_columns([
            # 手续费 (max of rate or min)
            pl.max_horizontal([
                pl.col('revenue') * self.commission_rate,
                pl.lit(self.min_commission)
            ]).alias('commission'),
            # 印花税
            (pl.col('revenue') * self.sell_tax).alias('tax'),
        ]).with_columns([
            # 净收入
            (pl.col('revenue') - pl.col('commission') - pl.col('tax')).alias('net_revenue'),
        ])
        
        # 计算盈亏 (需要成本信息)
        costs = []
        entry_dates = []
        holding_days = []
        
        for row in valid_sells.iter_rows(named=True):
            code = row['stock_code']
            pos_data = position_info.get(code, {})
            avg_cost = pos_data.get('cost', row[self._sell_price_type])
            entry_date = pos_data.get('entry_date', date_str)
            
            # 计算持有天数
            try:
                d1 = datetime.strptime(entry_date, '%Y-%m-%d')
                d2 = datetime.strptime(date_str, '%Y-%m-%d')
                days = (d2 - d1).days
            except:
                days = 0
            
            costs.append(avg_cost)
            entry_dates.append(entry_date)
            holding_days.append(days)
        
        valid_sells = valid_sells.with_columns([
            pl.Series('avg_cost', costs),
            pl.Series('entry_date', entry_dates),
            pl.Series('holding_days', holding_days),
        ]).with_columns([
            # 成本基础
            (pl.col('avg_cost') * pl.col('shares_held')).alias('cost_basis'),
        ]).with_columns([
            # 盈亏金额
            (pl.col('net_revenue') - pl.col('cost_basis')).alias('profit_loss'),
        ]).with_columns([
            # 收益率
            (pl.col('profit_loss') / pl.col('cost_basis') * 100).alias('roi'),
        ])
        
        # 更新组合和现金
        total_net_revenue = valid_sells['net_revenue'].sum()
        new_cash = cash + total_net_revenue
        
        # 更新持仓
        new_portfolio = portfolio.copy()
        new_position_info = position_info.copy()
        
        for row in valid_sells.iter_rows(named=True):
            code = row['stock_code']
            if code in new_portfolio:
                del new_portfolio[code]
            if code in new_position_info:
                del new_position_info[code]
        
        # 生成交易记录
        for row in valid_sells.iter_rows(named=True):
            trades.append({
                'date': date_str,
                'code': row['stock_code'],
                'action': 'sell',
                'shares': row['shares_held'],
                'price': row['open'],
                'revenue': row['net_revenue'],
                'commission': row['commission'],
                'tax': row['tax'],
                'profit_loss': row['profit_loss'],
                'roi': row['roi'],
                'entry_price': row['avg_cost'],
                'entry_date': row['entry_date'],
                'holding_days': row['holding_days'],
            })
        
        return {
            'portfolio': new_portfolio,
            'cash': new_cash,
            'position_info': new_position_info,
            'trades': trades
        }
    
    def _execute_buys_vectorized(
        self,
        buys: pl.DataFrame,
        portfolio: Dict[str, int],
        cash: float,
        date_str: str,
        max_positions: Optional[int] = None,
        position_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        向量化执行买入操作
        
        一次性计算所有买入的数量、金额、手续费
        【对齐传统执行】默认使用 10% 仓位，而非全仓
        """
        trades = []
        
        if buys.is_empty():
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': {},
                'trades': trades
            }
        
        # 过滤已持仓的股票
        portfolio_codes = set(portfolio.keys())
        
        # 构建过滤条件
        buy_filter_conditions = [
            ~pl.col('stock_code').is_in(list(portfolio_codes)),
            pl.col(self._buy_price_type) > 0,
        ]
        
        # 动态添加过滤条件（如果列存在）
        if 'is_suspended' in buys.columns:
            buy_filter_conditions.append(~pl.col('is_suspended').fill_null(False))
        if 'is_limit_up' in buys.columns:
            buy_filter_conditions.append(~pl.col('is_limit_up').fill_null(False))
        
        valid_buys = buys.filter(pl.all_horizontal(buy_filter_conditions))
        
        if valid_buys.is_empty():
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': {},
                'trades': trades
            }
        
        # 限制买入数量
        if max_positions is not None:
            current_count = len(portfolio)
            can_buy = max(0, max_positions - current_count)
            if can_buy == 0:
                return {
                    'portfolio': portfolio,
                    'cash': cash,
                    'position_info': {},
                    'trades': trades
                }
            valid_buys = valid_buys.head(can_buy)
        
        # 【对齐传统执行】默认使用 10% 仓位
        effective_position_ratio = position_ratio if position_ratio is not None else 0.1
        
        # 计算每只股票的投资金额
        num_buys = len(valid_buys)
        target_investment = cash * effective_position_ratio
        
        # 确保不超过可用现金
        if target_investment > cash:
            target_investment = cash
        
        # 如果投资金额过少，跳过
        if target_investment <= 1000:
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': {},
                'trades': trades
            }
        
        # 向量化计算买入数量
        # 【对齐传统执行】使用与传统逻辑相同的计算方式
        # shares = int(target_investment / (price * (1 + commission_rate)))
        # shares = (shares // 100) * 100
        valid_buys = valid_buys.with_columns([
            (pl.lit(target_investment) / (pl.col(self._buy_price_type) * (1 + self.commission_rate)))
            .floor().cast(pl.Int64).alias('shares_raw'),
        ]).with_columns([
            ((pl.col('shares_raw') / 100).floor() * 100).cast(pl.Int64).alias('shares'),
        ])
        
        # 过滤有效买入 (至少买 100 股)
        valid_buys = valid_buys.filter(pl.col('shares') >= 100)
        
        if valid_buys.is_empty():
            return {
                'portfolio': portfolio,
                'cash': cash,
                'position_info': {},
                'trades': trades
            }
        
        # 计算实际金额和费用
        valid_buys = valid_buys.with_columns([
            (pl.col('shares') * pl.col(self._buy_price_type)).alias('amount'),
        ]).with_columns([
            pl.max_horizontal([
                pl.col('amount') * self.commission_rate,
                pl.lit(self.min_commission)
            ]).alias('commission'),
        ]).with_columns([
            (pl.col('amount') + pl.col('commission')).alias('total_cost'),
        ])
        
        # 检查现金是否足够，逐个处理
        new_portfolio = portfolio.copy()
        new_position_info = {}
        remaining_cash = cash
        
        for row in valid_buys.iter_rows(named=True):
            total_cost = row['total_cost']
            
            if remaining_cash >= total_cost:
                # 执行买入
                code = row['stock_code']
                shares = row['shares']
                price = row['open']
                
                new_portfolio[code] = shares
                new_position_info[code] = {
                    'cost': price,
                    'entry_date': date_str
                }
                remaining_cash -= total_cost
                
                trades.append({
                    'date': date_str,
                    'code': code,
                    'action': 'buy',
                    'shares': shares,
                    'price': price,
                    'amount': row['amount'],
                    'commission': row['commission'],
                    'total_cost': total_cost,
                })
        
        return {
            'portfolio': new_portfolio,
            'cash': remaining_cash,
            'position_info': new_position_info,
            'trades': trades
        }
    
    def get_perf_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        calls = self._perf_stats['total_calls']
        return {
            'total_calls': calls,
            'total_duration': self._perf_stats['total_duration'],
            'avg_duration': self._perf_stats['total_duration'] / calls if calls > 0 else 0,
            'total_trades': self._perf_stats['total_trades'],
            'trades_per_call': self._perf_stats['total_trades'] / calls if calls > 0 else 0,
        }
    
    def print_perf_stats(self):
        """打印性能统计"""
        stats = self.get_perf_stats()
        print("=" * 60)
        print("向量化执行引擎性能统计")
        print("=" * 60)
        print(f"总调用次数: {stats['total_calls']}")
        print(f"总耗时: {stats['total_duration']:.3f} 秒")
        print(f"平均每次: {stats['avg_duration']*1000:.3f} ms")
        print(f"总交易数: {stats['total_trades']}")
        print(f"每次平均: {stats['trades_per_call']:.2f} 笔")
        print("=" * 60)


# ==================== 便捷函数 ====================

def create_executor(
    commission_rate: float = 0.0003,
    min_commission: float = 5.0,
    sell_tax: float = 0.001
) -> VectorizedExecutionEngine:
    """创建默认执行引擎"""
    return VectorizedExecutionEngine(
        commission_rate=commission_rate,
        min_commission=min_commission,
        sell_tax=sell_tax
    )


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("向量化交易执行引擎测试")
    print("=" * 60)
    
    # 创建测试数据
    test_pool = pl.DataFrame({
        'stock_code': ['000001.SZ', '000002.SZ', '000003.SZ', '000004.SZ'],
        'open': [10.0, 20.0, 30.0, 40.0],
        'close': [10.5, 19.5, 31.0, 39.0],
        'is_suspended': [False, False, False, False],
        'is_limit_up': [False, False, True, False],
        'is_limit_down': [False, False, False, False],
    })
    
    # 创建执行引擎
    executor = VectorizedExecutionEngine()
    
    # 测试场景 1: 买入
    print("\n[测试 1] 买入信号")
    signals_buy = {
        '000001.SZ': 'buy',
        '000002.SZ': 'buy',
    }
    
    portfolio, cash, trades, pos_info = executor.execute_trades(
        current_time=pd.Timestamp('2024-01-15'),
        stock_pool_pl=test_pool,
        signals=signals_buy,
        current_portfolio={},
        current_cash=1_000_000.0
    )
    
    print(f"  买入后现金: {cash:,.2f}")
    print(f"  持仓: {portfolio}")
    print(f"  交易数: {len(trades)}")
    for t in trades:
        print(f"    {t['code']}: 买入 {t['shares']}股 @ {t['price']:.2f}, "
              f"手续费 {t['commission']:.2f}")
    
    # 测试场景 2: 卖出
    print("\n[测试 2] 卖出信号")
    signals_sell = {
        '000001.SZ': 'sell',
    }
    
    # 先设置持仓成本
    position_info = {
        '000001.SZ': {'cost': 9.5, 'entry_date': '2024-01-01'}
    }
    
    portfolio2, cash2, trades2, pos_info2 = executor.execute_trades(
        current_time=pd.Timestamp('2024-01-16'),
        stock_pool_pl=test_pool,
        signals=signals_sell,
        current_portfolio=portfolio,
        current_cash=cash,
        position_info=position_info
    )
    
    print(f"  卖出后现金: {cash2:,.2f}")
    print(f"  持仓: {portfolio2}")
    print(f"  交易数: {len(trades2)}")
    for t in trades2:
        print(f"    {t['code']}: 卖出 {t['shares']}股 @ {t['price']:.2f}, "
              f"盈亏 {t['profit_loss']:.2f} ({t['roi']:.2f}%)")
    
    # 测试场景 3: 涨停不能买入
    print("\n[测试 3] 涨停过滤")
    signals_limit = {
        '000003.SZ': 'buy',  # 涨停
    }
    
    portfolio3, cash3, trades3, _ = executor.execute_trades(
        current_time=pd.Timestamp('2024-01-17'),
        stock_pool_pl=test_pool,
        signals=signals_limit,
        current_portfolio={},
        current_cash=1_000_000.0
    )
    
    print(f"  涨停股票买入交易数: {len(trades3)} (应该为 0)")
    
    # 性能统计
    print("\n")
    executor.print_perf_stats()
    
    print("\n测试完成!")
