"""
MA交叉策略完整回测 - 2025.1.1-2026.1.1
对比聚宽结果

关键修改：
1. 信号在T日生成，但标记为T+1日执行
2. 金叉条件：T-2时MA5<=MA10 且 T-1时MA5>MA10
3. 死叉条件：T-2时MA5>=MA10 且 T-1时MA5<MA10
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


class MACrossStrategyJoinQuant:
    """MA交叉策略 - 聚宽兼容版"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_JoinQuant"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（聚宽兼容）"
        self.ma_fast = None
        self.ma_slow = None
        self.target_idx = None
    
    def generate_signals_vectorized(
        self,
        price_matrix: np.ndarray,
        stock_codes: List[str],
        trading_dates: List[str],
        preloaded_data: Optional[Dict[str, Any]] = None,
        data_query=None,
        price_matrix_adj: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        向量化信号生成 - 聚宽兼容版
        
        聚宽逻辑：
        - 信号在T-1日收盘后生成
        - T日开盘执行
        - 所以信号矩阵需要延迟一天
        
        金叉条件：T-2时MA5<=MA10 且 T-1时MA5>MA10
        死叉条件：T-2时MA5>=MA10 且 T-1时MA5<MA10
        """
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        price_matrix_for_indicator = price_matrix_adj if price_matrix_adj is not None else price_matrix
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        if self.target_idx is None:
            return signals
        
        close_prices_adj = price_matrix_for_indicator[:, :, 3]
        n = self.target_idx
        prices = close_prices_adj[:, n]
        
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
        
        # 聚宽逻辑：信号延迟一天执行
        # 在T日收盘后，检查T-1和T的MA交叉
        # 如果交叉，则T+1日开盘执行
        print(f"\n【策略调试】trading_dates长度: {len(trading_dates)}")
        print(f"  2025-02-05 索引: {trading_dates.index('2025-02-05') if '2025-02-05' in trading_dates else -1}")
        print(f"  2025-02-07 索引: {trading_dates.index('2025-02-07') if '2025-02-07' in trading_dates else -1}")
        print(f"  2025-02-10 索引: {trading_dates.index('2025-02-10') if '2025-02-10' in trading_dates else -1}")
        
        for t in range(1, T - 1):  # t从1开始，因为需要检查t-1
            if np.isnan(self.ma_fast[t]) or np.isnan(self.ma_slow[t]):
                continue
            if np.isnan(self.ma_fast[t-1]) or np.isnan(self.ma_slow[t-1]):
                continue
            
            curr_fast = self.ma_fast[t]
            curr_slow = self.ma_slow[t]
            prev_fast = self.ma_fast[t-1]
            prev_slow = self.ma_slow[t-1]
            
            # 金叉：T-1时MA5<=MA10 且 T时MA5>MA10
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signals[t + 1, n] = 1  # T+1日执行
                if '2025-02-05' <= trading_dates[t] <= '2025-02-15':
                    print(f"  金叉 @ 索引{t} ({trading_dates[t]}): signals[{t+1}] = 1 ({trading_dates[t+1]})")
            # 死叉：T-1时MA5>=MA10 且 T时MA5<MA10
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signals[t + 1, n] = -1  # T+1日执行
                if '2025-02-05' <= trading_dates[t] <= '2025-02-15':
                    print(f"  死叉 @ 索引{t} ({trading_dates[t]}): signals[{t+1}] = -1 ({trading_dates[t+1]})")
        
        return signals


print("=" * 70)
print("MA交叉策略完整回测 - 2025.1.1-2026.1.1（聚宽兼容版）")
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
    engine = UnifiedBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyJoinQuant(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2025-01-01 ~ 2026-01-01")
    print(f"   初始资金: {config.initial_capital}")
    print(f"   仓位比例: {config.position_ratio}")
    
    trades = []
    final_result = None
    
    for event in engine.run_backtest('2025-01-01', '2026-01-01', strategy):
        if event['type'] == 'new_trade_engine':
            trade = event['data']
            trades.append(trade)
            print(f"[Trade] {trade['date']} {trade['action']:6} {trade['code']} "
                  f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")
        elif event['type'] == 'stream_complete':
            final_result = event['data']
    
    if final_result:
        print("\n" + "=" * 70)
        print("AquaTrade 回测结果")
        print("=" * 70)
        print(f"策略收益: {final_result['totalReturn']:.2f}%")
        print(f"策略年化收益: {final_result['annualizedReturn']:.2f}%")
        print(f"基准收益: {final_result.get('benchmarkReturn', 0):.2f}%")
        print(f"阿尔法: {final_result.get('alpha', 0):.3f}")
        print(f"贝塔: {final_result.get('beta', 0):.3f}")
        print(f"夏普比率: {final_result['sharpeRatio']:.3f}")
        print(f"胜率: {final_result['winRate']:.1f}%")
        print(f"盈亏比: {final_result.get('profitFactor', 0):.3f}")
        print(f"最大回撤: {final_result['maxDrawdown']:.2f}%")
        print(f"索提诺比率: {final_result['sortinoRatio']:.3f}")
        print(f"总交易次数: {final_result['totalTrades']}")
        
        print("\n" + "=" * 70)
        print("聚宽回测结果（参考）")
        print("=" * 70)
        print("策略收益: 5.24%")
        print("策略年化收益: 5.40%")
        print("基准收益: 17.66%")
        print("阿尔法: 0.004")
        print("贝塔: 0.070")
        print("夏普比率: 0.146")
        print("胜率: 33.3%")
        print("盈亏比: 1.790")
        print("最大回撤: 10.10%")
        print("索提诺比率: 0.196")
        
        print("\n" + "=" * 70)
        print("差异分析")
        print("=" * 70)
        diff_return = final_result['totalReturn'] - 5.24
        print(f"收益率差异: {diff_return:.2f}%")
        if abs(diff_return) < 0.5:
            print("✓ 收益率差异小于0.5%，结果基本一致")
        else:
            print("✗ 收益率差异较大，需要进一步分析")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
