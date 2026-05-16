"""
MA交叉策略回测 - 自己计算MA（调试版4 - 详细追踪买入逻辑）
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


class MACrossStrategyCalcDebug:
    """MA交叉策略 - 自己计算MA值"""
    
    def __init__(self, fast_period=5, slow_period=10):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"MA{fast_period}_MA{slow_period}_Cross_Calc_Debug"
        self.description = f"MA{fast_period}/MA{slow_period}交叉策略（自己计算MA-调试版）"
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
        """向量化信号生成 - 自己计算MA"""
        T, N, _ = price_matrix.shape
        signals = np.zeros((T, N), dtype=np.int8)
        
        if self.target_idx is None:
            for i, code in enumerate(stock_codes):
                if code == '000001':
                    self.target_idx = i
                    break
        
        close_prices = price_matrix[:, :, 3]
        self.ma_fast = np.full_like(close_prices, np.nan)
        self.ma_slow = np.full_like(close_prices, np.nan)
        
        for n in range(N):
            prices = close_prices[:, n]
            valid_mask = ~np.isnan(prices)
            if np.sum(valid_mask) < self.slow_period:
                continue
            
            prices_valid = prices[valid_mask]
            prices_series = pd.Series(prices_valid)
            ma_fast_series = prices_series.rolling(window=self.fast_period).mean()
            ma_slow_series = prices_series.rolling(window=self.slow_period).mean()
            
            self.ma_fast[valid_mask, n] = ma_fast_series.values
            self.ma_slow[valid_mask, n] = ma_slow_series.values
        
        for t in range(1, T):
            for n in range(N):
                if np.isnan(self.ma_fast[t-1, n]) or np.isnan(self.ma_slow[t-1, n]):
                    continue
                
                if t >= 2 and not np.isnan(self.ma_fast[t-2, n]) and not np.isnan(self.ma_slow[t-2, n]):
                    prev_fast = self.ma_fast[t-1, n]
                    prev_slow = self.ma_slow[t-1, n]
                    prev2_fast = self.ma_fast[t-2, n]
                    prev2_slow = self.ma_slow[t-2, n]
                    
                    date = trading_dates[t]
                    
                    if prev2_fast < prev2_slow and prev_fast > prev_slow:
                        signals[t, n] = 1
                        if n == self.target_idx:
                            print(f"[Signal] 金叉 @ {date}")
                    
                    elif prev2_fast > prev2_slow and prev_fast < prev_slow:
                        signals[t, n] = -1
                        if n == self.target_idx:
                            print(f"[Signal] 死叉 @ {date}")
        
        return signals


# 创建一个包装器来详细追踪买入逻辑
class DebugBacktestEngine(UnifiedBacktestEngine):
    def _execute_trades(self, current_time, stock_pool, signals, portfolio, cash, position_info, data_dict):
        """包装交易执行以添加详细调试信息"""
        import polars as pl
        
        date_str = current_time.strftime("%Y-%m-%d")
        
        # 只关注2025-01-21的000001
        if date_str == '2025-01-21' and '000001' in signals:
            print(f"\n[TradeDebug] ===== {date_str} 000001买入信号详细追踪 =====")
            print(f"[TradeDebug] 信号: {signals['000001']}")
            print(f"[TradeDebug] 当前持仓: {portfolio}")
            print(f"[TradeDebug] 当前现金: {cash}")
            print(f"[TradeDebug] 000001数据: {data_dict.get('000001', {})}")
            
            # 手动检查买入条件
            signal = signals['000001']
            sig_type = signal.get('action') if isinstance(signal, dict) else signal
            print(f"[TradeDebug] 信号类型: {sig_type}")
            
            if sig_type in ('buy', 'enter'):
                print(f"[TradeDebug] ✓ 是买入信号")
                
                # 检查持仓限制
                current_positions_count = len(portfolio)
                max_positions = self.config.max_positions
                print(f"[TradeDebug] 当前持仓数: {current_positions_count}, max_positions: {max_positions}")
                
                if max_positions is not None and current_positions_count >= max_positions:
                    print(f"[TradeDebug] ✗ 持仓限制阻止买入")
                else:
                    print(f"[TradeDebug] ✓ 持仓限制检查通过")
                
                # 检查单日买入限制
                max_stocks_per_day = self.config.max_stocks_per_day
                print(f"[TradeDebug] max_stocks_per_day: {max_stocks_per_day}")
                
                # 检查是否已持仓
                if portfolio.get('000001', 0) > 0:
                    print(f"[TradeDebug] ✗ 已持仓，跳过")
                else:
                    print(f"[TradeDebug] ✓ 未持仓")
                
                # 检查数据
                if '000001' not in data_dict:
                    print(f"[TradeDebug] ✗ 无000001数据")
                else:
                    print(f"[TradeDebug] ✓ 有000001数据")
                    data = data_dict['000001']
                    price = float(data.get('open', 0))
                    is_suspended = bool(data.get('is_suspended', 0))
                    is_limit_up = bool(data.get('is_limit_up', 0))
                    
                    print(f"[TradeDebug] 开盘价: {price}, 停牌: {is_suspended}, 涨停: {is_limit_up}")
                    
                    if price <= 0:
                        print(f"[TradeDebug] ✗ 价格<=0")
                    elif is_suspended:
                        print(f"[TradeDebug] ✗ 停牌")
                    elif is_limit_up:
                        print(f"[TradeDebug] ✗ 涨停")
                    else:
                        print(f"[TradeDebug] ✓ 价格检查通过")
                        
                        # 计算买入金额
                        target_investment = cash * self.config.position_ratio
                        print(f"[TradeDebug] position_ratio: {self.config.position_ratio}")
                        print(f"[TradeDebug] 目标投资金额: {target_investment}")
                        
                        if target_investment > cash:
                            target_investment = cash
                        
                        if target_investment <= 1000:
                            print(f"[TradeDebug] ✗ 投资金额<=1000")
                        else:
                            print(f"[TradeDebug] ✓ 投资金额检查通过")
                            
                            # 计算股数
                            shares = int(target_investment / (price * (1 + self.config.commission_rate)))
                            shares = (shares // 100) * 100
                            print(f"[TradeDebug] 计算股数: {shares}")
                            
                            if shares >= 100:
                                cost = shares * price
                                commission = max(cost * self.config.commission_rate, self.config.min_commission)
                                total_outlay = cost + commission
                                print(f"[TradeDebug] 成本: {cost}, 佣金: {commission}, 总支出: {total_outlay}")
                                
                                if total_outlay <= cash:
                                    print(f"[TradeDebug] ✓ 应该执行买入!")
                                else:
                                    print(f"[TradeDebug] ✗ 资金不足")
                            else:
                                print(f"[TradeDebug] ✗ 股数<100")
        
        # 调用父类方法
        result = super()._execute_trades(current_time, stock_pool, signals, portfolio, cash, position_info, data_dict)
        
        # 检查交易结果
        new_portfolio, new_cash, trades = result
        if date_str == '2025-01-21' and '000001' in signals:
            print(f"[TradeDebug] 交易执行结果: {len(trades)}笔交易")
            for trade in trades:
                print(f"[TradeDebug] 交易: {trade}")
            print(f"[TradeDebug] 新持仓: {new_portfolio}")
            print(f"[TradeDebug] 新现金: {new_cash}")
        
        return result


print("=" * 70)
print("MA交叉策略回测 - 自己计算MA（调试版4）")
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
    engine = DebugBacktestEngine(data_query, config=config)
    
    strategy = MACrossStrategyCalcDebug(fast_period=5, slow_period=10)
    
    print("\n[2] 运行回测...")
    print(f"   策略: {strategy.description}")
    print(f"   回测区间: 2025-01-01 ~ 2025-01-31")
    
    results = []
    trades = []
    
    for event in engine.run_backtest('2025-01-01', '2025-01-31', strategy):
        if event['type'] == 'backtest_complete':
            results.append(event['data'])
        elif event['type'] == 'trade':
            trade = event['data']
            trades.append(trade)
    
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
        if trade['stock_code'] == '000001':
            print(f"   >>> {trade['date']} {trade['action']:6} {trade['stock_code']} "
                  f"价格:{trade['price']:.2f} 数量:{trade['quantity']} <<<")
        else:
            print(f"   {trade['date']} {trade['action']:6} {trade['stock_code']} "
                  f"价格:{trade['price']:.2f} 数量:{trade['quantity']}")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
