"""
MA交叉策略回测 - 最终版本2（只交易000001）
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
    """
    MA交叉策略 - 只交易000001
    """
    
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
        
        # 找到000001的索引
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            print("[Strategy] 警告: 未找到000001")
            return signals
        
        # 提取收盘价
        close_prices = price_matrix[:, :, 3]
        
        # 只计算000001的MA
        n = self.target_idx
        prices = close_prices[:, n]
        
        valid_mask = ~np.isnan(prices)
        if np.sum(valid_mask) < self.slow_period:
            print("[Strategy] 警告: 000001数据不足")
            return signals
        
        # 计算MA5和MA10
        prices_valid = prices[valid_mask]
        prices_series = pd.Series(prices_valid)
        ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
        ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
        
        self.ma_fast = np.full(T, np.nan)
        self.ma_slow = np.full(T, np.nan)
        self.ma_fast[valid_mask] = ma_fast_series.values
        self.ma_slow[valid_mask] = ma_slow_series.values
        
        # 计算金叉死叉 - 只针对000001
        for t in range(1, T):
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            if t >= 2 and not np.isnan(self.ma_fast[t-2]) and not np.isnan(self.ma_slow[t-2]):
                prev_fast = self.ma_fast[t-1]
                prev_slow = self.ma_slow[t-1]
                prev2_fast = self.ma_fast[t-2]
                prev2_slow = self.ma_slow[t-2]
                
                date = trading_dates[t]
                
                # 金叉
                if prev2_fast < prev2_slow and prev_fast > prev_slow:
                    signals[t, n] = 1
                    print(f"[Signal] 金叉 @ {date}: 前日MA5={prev2_fast:.4f}, 前日MA10={prev2_slow:.4f}, "
                          f"昨日MA5={prev_fast:.4f}, 昨日MA10={prev_slow:.4f}")
                
                # 死叉
                elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                    signals[t, n] = -1
                    print(f"[Signal] 死叉 @ {date}: 前日MA5={prev2_fast:.4f}, 前日MA10={prev2_slow:.4f}, "
                          f"昨日MA5={prev_fast:.4f}, 昨日MA10={prev_slow:.4f}")
        
        return signals


print("=" * 70)
print("MA交叉策略回测 - 最终版本2（只交易000001）")
print("=" * 70)

try:
    print("\n[1] 初始化...")
    data_query = OptimizedStockDataQuery()
    
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.0003,
        warmup_days=30,
        position_ratio=0.9  # 使用90%资金
    )
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyCalc(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    print(f"   初始资金: {config.initial_capital}")
    print(f"   仓位比例: {config.position_ratio}")
    
    results = []
    trades = []
    
    for event in engine.run_backtest('2025-01-01', '2025-01-31', strategy):
        if event['type'] == 'backtest_complete':
            results.append(event['data'])
        elif event['type'] == 'trade':
            trade = event['data']
            trades.append(trade)
            print(f"[Trade] {trade['date']} {trade['action']:6} {trade['stock_code']} "
                  f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
    
    print("\n[3] 回测结果:")
    if results:
        result = results[-1]
        print(f"   初始资金: {result.get('initial_capital', 100000):.2f}")
        print(f"   最终资金: {result.get('final_value', 0):.2f}")
        print(f"   总收益率: {result.get('total_return', 0):.2%}")
        print(f"   交易次数: {result.get('total_trades', 0)}")
    else:
        print("   无结果")
    
    print(f"\n[4] 交易记录 ({len(trades)}笔):")
    for trade in trades:
        print(f"   {trade['date']} {trade['action']:6} {trade['stock_code']} "
              f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
    
    # 对比聚宽
    print("\n[5] 与聚宽对比:")
    print("   聚宽买入: 2025-01-21 价格约11.33 数量约7900股")
    print("   聚宽卖出: 2025-01-24 价格约11.34")
    
    if trades:
        buy_trade = [t for t in trades if t['action'] == 'buy']
        sell_trade = [t for t in trades if t['action'] == 'sell']
        
        if buy_trade:
            print(f"   AquaTrade买入: {buy_trade[0]['date']} 价格:{buy_trade[0]['price']:.2f} "
                  f"数量:{buy_trade[0]['quantity']}")
        if sell_trade:
            print(f"   AquaTrade卖出: {sell_trade[0]['date']} 价格:{sell_trade[0]['price']:.2f} "
                  f"数量:{sell_trade[0]['quantity']}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
