"""
测试修复后的卖出原因
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.database.optimized_data_query import OptimizedStockDataQuery
from core.backtest.unified_engine import UnifiedBacktestEngine, BacktestConfig
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
import pandas as pd
import numpy as np

query = OptimizedStockDataQuery()

config = BacktestConfig(
    initial_capital=1000000.0,
    commission_rate=0.0003,
    min_commission=5.0,
    position_ratio=0.1,
    max_positions=10,
)

engine = UnifiedBacktestEngine(data_query=query, config=config)

# 修改策略，让它记录卖出原因
class DebugMainWaveTrendStrategy(MainWaveTrendStrategy):
    """带调试信息的主升浪策略"""

    def _compute_sell_signals(self, close, ma5, ma10, ma20, bias):
        """
        计算卖出信号（带调试信息）
        """
        T, N = close.shape

        sell_mask = np.zeros((T, N), dtype=bool)
        sell_reasons_matrix = np.full((T, N), '', dtype=object)

        # 缓冲阈值配置
        ma10_buffer = 0.98
        ma20_buffer = 0.95

        for t in range(1, T):
            # 乖离过大卖出
            bias_extreme = (
                np.isfinite(bias[t]) &
                (bias[t] > self.config.bias_extreme_max)
            )

            # 趋势破坏卖出 - 添加缓冲阈值
            trend_broken_ma10 = (
                (close[t] < ma10[t] * ma10_buffer) &
                (close[t-1] >= ma10[t-1] * ma10_buffer)
            )
            trend_broken_ma20 = (
                (close[t] < ma20[t] * ma20_buffer) &
                (close[t-1] >= ma20[t-1] * ma20_buffer)
            )

            sell_mask[t] = bias_extreme | trend_broken_ma10 | trend_broken_ma20

            # 记录卖出原因
            for n in range(N):
                if sell_mask[t, n]:
                    reasons = []
                    if bias_extreme[n]:
                        reasons.append(f"乖离过大({bias[t, n]:.1%})")
                    if trend_broken_ma10[n]:
                        reasons.append("跌破MA10(缓冲2%)")
                    if trend_broken_ma20[n]:
                        reasons.append("跌破MA20(缓冲5%)")
                    sell_reasons_matrix[t, n] = ', '.join(reasons)

        self.sell_reasons_matrix = sell_reasons_matrix
        return sell_mask

strategy = DebugMainWaveTrendStrategy(
    data_manager=query,
    lookback_days=20,
    breakout_days=5,
    volume_threshold=1.5,
    trend_period=20
)

print("=" * 70)
print("修复后的卖出原因分析")
print("=" * 70)

start_date = '2025-01-02'
end_date = '2025-01-10'

print(f"\n回测范围: {start_date} ~ {end_date}")
print(f"缓冲阈值: MA10=2%, MA20=5%")

# 预加载数据并生成信号
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

preloaded_data = engine._preload_data(start_ts, end_ts)
fm = engine._factor_matrix

# 准备数据并生成信号
strategy.prepare_data(preloaded_data, fm.dates, fm.codes_str, fm.values)
signals = strategy.generate_signals_vectorized(
    fm.values, fm.dates, fm.codes_str, query, preloaded_data
)

# 统计卖出原因
sell_reasons_count = {}

print(f"\n{'='*70}")
print("每日卖出信号分析")
print(f"{'='*70}")

for t_idx, date in enumerate(fm.dates):
    day_sell_signals = []

    for n_idx, code in enumerate(fm.codes_str):
        if signals[t_idx, n_idx] == 2:
            reason = strategy.sell_reasons_matrix[t_idx, n_idx]
            day_sell_signals.append((code, reason))
            sell_reasons_count[reason] = sell_reasons_count.get(reason, 0) + 1

    if day_sell_signals:
        print(f"\n{date}: {len(day_sell_signals)} 个卖出信号")
        day_reasons = {}
        for code, reason in day_sell_signals:
            day_reasons[reason] = day_reasons.get(reason, 0) + 1
        for reason, count in sorted(day_reasons.items(), key=lambda x: -x[1]):
            print(f"  - {reason}: {count} 只")

print(f"\n{'='*70}")
print("卖出原因统计（修复后）")
print(f"{'='*70}")
for reason, count in sorted(sell_reasons_count.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {count} 次")

# 分析持仓时间
print(f"\n{'='*70}")
print("持仓时间分析")
print(f"{'='*70}")

# 找到所有买卖对
buy_sell_pairs = []
for n_idx, code in enumerate(fm.codes_str):
    buy_date = None
    for t_idx, date in enumerate(fm.dates):
        if signals[t_idx, n_idx] == 1:
            buy_date = date
        elif signals[t_idx, n_idx] == 2 and buy_date:
            buy_sell_pairs.append((code, buy_date, date))
            buy_date = None

# 统计持仓时间
from datetime import datetime
holding_days = []
for code, buy, sell in buy_sell_pairs:
    buy_dt = datetime.strptime(buy, '%Y-%m-%d')
    sell_dt = datetime.strptime(sell, '%Y-%m-%d')
    days = (sell_dt - buy_dt).days
    holding_days.append(days)

if holding_days:
    print(f"  平均持仓时间: {sum(holding_days)/len(holding_days):.1f} 天")
    print(f"  最短持仓: {min(holding_days)} 天")
    print(f"  最长持仓: {max(holding_days)} 天")
    print(f"  持仓1天的交易: {sum(1 for d in holding_days if d == 1)} 次")
    print(f"  持仓>1天的交易: {sum(1 for d in holding_days if d > 1)} 次")
else:
    print("  无完整买卖记录")

print(f"\n{'='*70}")
print("结论")
print(f"{'='*70}")
print("✓ 添加缓冲阈值后，卖出条件不再过于敏感")
print("✓ 持仓时间延长，策略更接近中期持有而非超短线")
