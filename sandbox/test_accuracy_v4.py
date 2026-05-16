"""回测精准性测试 V4 - 在引擎中添加调试"""
import sys
sys.path.insert(0, 'c:\\Users\\Liu\\Desktop\\projects\\aquatrade')

import numpy as np
import pandas as pd
import time

from core.strategies.vectorized_base import VectorizedStrategyBase
from data_svc.database.polars_data_loader_v5 import get_polars_loader_v5
from config.logger import get_logger


class TestStrategy(VectorizedStrategyBase):
    strategy_name = "TestStrategy"
    
    def __init__(self, signal_day=None):
        super().__init__()
        self.signal_day = signal_day
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data=None):
        T, N = len(trading_dates), len(stock_codes)
        signals = np.zeros((T, N), dtype=np.int32)
        
        if self.signal_day is not None and self.signal_day < T:
            signals[self.signal_day, 0] = 1
            if self.signal_day + 5 < T:
                signals[self.signal_day + 5, 0] = 2
        
        return signals


def test_with_debug():
    """带调试的回测测试"""
    print("\n" + "=" * 70)
    print("回测精准性测试 V4 - 带调试")
    print("=" * 70)
    
    from dataclasses import dataclass
    from typing import List, Dict, Optional, Iterator
    from datetime import datetime
    
    @dataclass
    class FastBacktestConfig:
        initial_capital: float = 1000000.0
        commission_rate: float = 0.0003
    
    @dataclass
    class FastBacktestDailyResult:
        date: datetime
        total_value: float
        cash: float
        positions: Dict[str, float]
        trades: List[Dict]
        metrics: Dict
    
    config = FastBacktestConfig(initial_capital=1000000, commission_rate=0.0003)
    strategy = TestStrategy(signal_day=10)
    
    # 加载数据
    loader = get_polars_loader_v5()
    matrix_data = loader.load_period_to_matrix(
        "2023-01-01", "2023-03-31",
        required_fields=['open', 'high', 'low', 'close', 'volume']
    )
    
    matrices = matrix_data['matrices']
    trading_dates = matrix_data['trading_dates']
    stock_codes = matrix_data['stock_codes']
    T, N = matrix_data['T'], matrix_data['N']
    
    print(f"\n数据信息:")
    print(f"  交易日数: {T}")
    print(f"  股票数: {N}")
    print(f"  第一只股票代码: {stock_codes[0]}")
    
    # 构建价格矩阵
    price_matrix = np.stack([
        matrices['open'], matrices['high'], matrices['low'],
        matrices['close'], matrices['volume']
    ], axis=2)
    
    # 生成信号
    signal_matrix = strategy.generate_signals_vectorized(
        price_matrix, trading_dates, stock_codes, None, None
    )
    
    # 回测执行（带调试）
    cash = config.initial_capital
    positions = np.zeros(N, dtype=np.float32)
    open_prices = matrices['open']
    close_prices = matrices['close']
    valid_prices = ~np.isnan(open_prices) & (open_prices > 0)
    
    results = []
    
    for t in range(T):
        date_str = trading_dates[t]
        signals = signal_matrix[t]
        today_open = open_prices[t]
        today_close = close_prices[t]
        valid = valid_prices[t]
        
        position_value = np.nansum(positions * today_close)
        total_value = cash + position_value
        
        # 卖出
        sell_mask = (signals == 2) & (positions > 0) & valid
        if sell_mask.any():
            sell_prices = today_open[sell_mask]
            sell_shares = positions[sell_mask]
            sell_value = np.nansum(sell_shares * sell_prices)
            cash += sell_value * (1 - config.commission_rate)
            positions[sell_mask] = 0
        
        # 买入（带调试）
        buy_mask = (signals == 1) & (positions == 0) & valid
        if buy_mask.any():
            print(f"\n=== 第{t}天 ({date_str}) 买入调试 ===")
            print(f"买入前现金: {cash:,.2f}")
            
            n_buys = buy_mask.sum()
            available_cash = cash * 0.95 / (1 + config.commission_rate)
            cash_per_stock = available_cash / n_buys
            
            print(f"可用资金: {available_cash:,.2f}")
            print(f"每只股票可用: {cash_per_stock:,.2f}")
            
            buy_prices = today_open[buy_mask]
            print(f"买入价格: {buy_prices}")
            
            shares = (cash_per_stock / buy_prices / 100).astype(int) * 100
            shares = np.maximum(shares, 0)
            print(f"买入股数: {shares}")
            
            stock_costs = shares * buy_prices
            commissions = stock_costs * config.commission_rate
            total_cost = np.sum(stock_costs) + np.sum(commissions)
            
            print(f"股票成本: {stock_costs}")
            print(f"佣金: {commissions}")
            print(f"总成本: {total_cost:,.2f}")
            
            if total_cost <= cash and total_cost > 0:
                positions[buy_mask] = shares
                cash -= total_cost
                print(f"买入后现金: {cash:,.2f}")
        
        position_value = np.nansum(positions * today_close)
        total_value = cash + position_value
        
        result = FastBacktestDailyResult(
            date=pd.to_datetime(date_str),
            total_value=total_value,
            cash=cash,
            positions={code: float(positions[i]) for i, code in enumerate(stock_codes) if positions[i] > 0},
            trades=[],
            metrics={'position_value': position_value}
        )
        results.append(result)
    
    # 分析结果
    print("\n=== 结果分析 ===")
    for i, r in enumerate(results):
        if r.positions:
            print(f"\n第{i}天 ({r.date.strftime('%Y-%m-%d')}):")
            print(f"  持仓: {r.positions}")
            print(f"  持仓市值: {r.metrics['position_value']:,.2f}")
            print(f"  现金: {r.cash:,.2f}")
            print(f"  总资产: {r.total_value:,.2f}")
            break


if __name__ == "__main__":
    test_with_debug()
