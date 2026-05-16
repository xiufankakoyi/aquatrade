"""
MA交叉策略回测 - 全年回测（2025-01-01 到 2026-01-01）
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List

from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


class MACrossStrategyCalc:
    """MA交叉策略 - 只交易000001"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_Cross_000001"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（只交易000001）"
        self.ma_fast = None
        self.ma_slow = None
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None
    ) -> np.ndarray:
        """向量化信号生成 - 只生成000001的信号"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        close_prices = price_matrix[:, :, 3]
        n = self.target_idx
        prices = close_prices[:, n]
        
        valid_mask = ~np.isnan(prices)
        if np.sum(valid_mask) < self.slow_period:
            return signals
        
        prices_valid = prices[valid_mask]
        prices_series = pd.Series(prices_valid)
        ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
        ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
        
        self.ma_fast = np.full(T, np.nan)
        self.ma_slow = np.full(T, np.nan)
        self.ma_fast[valid_mask] = ma_fast_series.values
        self.ma_slow[valid_mask] = ma_slow_series.values
        
        for t in range(1, T):
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            if t >= 2 and not np.isnan(self.ma_fast[t-2]) and not np.isnan(self.ma_slow[t-2]):
                prev_fast = self.ma_fast[t-1]
                prev_slow = self.ma_slow[t-1]
                prev2_fast = self.ma_fast[t-2]
                prev2_slow = self.ma_slow[t-2]
                
                date = trading_dates[t]
                
                if prev2_fast < prev2_slow and prev_fast > prev_slow:
                    signals[t, n] = 1
                    print(f"[Signal] 金叉 @ {date}")
                elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                    signals[t, n] = -1
                    print(f"[Signal] 死叉 @ {date}")
        
        return signals


# 创建一个使用收盘价交易的引擎
class ClosePriceBacktestEngine(UnifiedBacktestEngine):
    def _execute_trades(self, current_time, stock_pool, signals, portfolio, cash, position_info, data_dict):
        """使用收盘价进行交易"""
        date_str = current_time.strftime("%Y-%m-%d")
        
        # 修改数据字典中的价格使用收盘价
        modified_data_dict = {}
        for code, data in data_dict.items():
            modified_data = dict(data)
            # 使用收盘价作为交易价格
            if 'close' in modified_data:
                modified_data['open'] = modified_data['close']
            modified_data_dict[code] = modified_data
        
        # 调用父类方法
        return super()._execute_trades(current_time, stock_pool, signals, portfolio, cash, position_info, modified_data_dict)


print("=" * 70)
print("MA交叉策略回测 - 全年回测（2025-01-01 到 2026-01-01）")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9
    )
    engine = ClosePriceBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyCalc(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print(f"   初始资金: {config.initial_capital}")
    print(f"   仓位比例: {config.position_ratio}")
    print(f"   交易价格: 收盘价")
    
    trades = []
    daily_equity = []
    
    for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
        if event['type'] == 'new_trade_engine':
            trade = event['data']
            trades.append(trade)
            if trade['code'] == '000001':
                print(f"[Trade] {trade['date']} {trade['action']:6} {trade['code']} "
                      f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
        elif event['type'] == 'daily_equity_engine':
            daily_equity.append({
                'date': event['data']['date'],
                'equity': event['data']['equity']
            })
    
    # 计算回测结果
    print("\n[3] 回测结果:")
    
    # 获取000001的交易
    trades_000001 = [t for t in trades if t['code'] == '000001']
    
    if trades_000001:
        initial_capital = 100000
        
        # 计算最终资金
        if daily_equity:
            final_value = daily_equity[-1]['equity']
        else:
            final_value = initial_capital
        
        total_return = (final_value - initial_capital) / initial_capital
        
        print(f"   初始资金: {initial_capital:.2f}")
        print(f"   最终资金: {final_value:.2f}")
        print(f"   总收益率: {total_return:.2%}")
        print(f"   交易次数: {len(trades_000001)}")
    else:
        print("   无交易")
    
    print(f"\n[4] 000001交易记录 ({len(trades_000001)}笔):")
    for trade in trades_000001:
        print(f"   {trade['date']} {trade['action']:6} {trade['code']} "
              f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
    
    # 对比聚宽
    print("\n[5] 与聚宽对比:")
    print(f"   聚宽收益率: 5.24%")
    
    if trades_000001:
        if daily_equity:
            final_value = daily_equity[-1]['equity']
            total_return = (final_value - 100000) / 100000
            print(f"   AquaTrade收益率: {total_return:.2%}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
