"""
调试卖出原因 - 分析为什么持仓时间很短
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
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sell_reasons = []  # 记录卖出原因
    
    def _compute_sell_signals(self, close, ma5, ma10, ma20, bias):
        """
        计算卖出信号（带调试信息）
        """
        T, N = close.shape
        
        sell_mask = np.zeros((T, N), dtype=bool)
        sell_reasons_matrix = np.full((T, N), '', dtype=object)  # 记录卖出原因
        
        for t in range(1, T):
            # 乖离过大卖出
            bias_extreme = (
                np.isfinite(bias[t]) & 
                (bias[t] > self.config.bias_extreme_max)
            )
            
            # 趋势破坏卖出 - 跌破MA10
            trend_broken_ma10 = (
                (close[t] < ma10[t]) & 
                (close[t-1] >= ma10[t-1])
            )
            
            # 趋势破坏卖出 - 跌破MA20
            trend_broken_ma20 = (
                (close[t] < ma20[t]) & 
                (close[t-1] >= ma20[t-1])
            )
            
            # 合并卖出信号
            sell_mask[t] = bias_extreme | trend_broken_ma10 | trend_broken_ma20
            
            # 记录卖出原因
            for n in range(N):
                if sell_mask[t, n]:
                    reasons = []
                    if bias_extreme[n]:
                        reasons.append(f"乖离过大({bias[t, n]:.1%})")
                    if trend_broken_ma10[n]:
                        reasons.append("跌破MA10")
                    if trend_broken_ma20[n]:
                        reasons.append("跌破MA20")
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
print("调试卖出原因")
print("=" * 70)

start_date = '2025-01-02'
end_date = '2025-01-10'

print(f"\n回测范围: {start_date} ~ {end_date}")
print(f"卖出条件阈值:")
print(f"  - 乖离过大: > {strategy.config.bias_extreme_max:.1%}")
print(f"  - 趋势破坏: 跌破MA10或MA20")

# 预加载数据并生成信号
from datetime import datetime
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

preloaded_data = engine._preload_data(start_ts, end_ts)
fm = engine._factor_matrix

# 准备数据并生成信号
strategy.prepare_data(preloaded_data, fm.dates, fm.codes_str, fm.values)
signals = strategy.generate_signals_vectorized(
    fm.values, fm.dates, fm.codes_str, query, preloaded_data
)

print(f"\n信号矩阵形状: {signals.shape}")
print(f"日期列表: {fm.dates}")

# 统计卖出原因
sell_reasons_count = {
    '乖离过大': 0,
    '跌破MA10': 0,
    '跌破MA20': 0,
}

print(f"\n{'='*70}")
print("每日卖出信号分析")
print(f"{'='*70}")

for t_idx, date in enumerate(fm.dates):
    day_sell_signals = []
    
    for n_idx, code in enumerate(fm.codes_str):
        if signals[t_idx, n_idx] == 2:  # 卖出信号
            reason = strategy.sell_reasons_matrix[t_idx, n_idx]
            day_sell_signals.append((code, reason))
            
            # 统计原因
            if '乖离过大' in reason:
                sell_reasons_count['乖离过大'] += 1
            if '跌破MA10' in reason:
                sell_reasons_count['跌破MA10'] += 1
            if '跌破MA20' in reason:
                sell_reasons_count['跌破MA20'] += 1
    
    if day_sell_signals:
        print(f"\n{date}: {len(day_sell_signals)} 个卖出信号")
        # 统计当天的卖出原因
        day_reasons = {}
        for code, reason in day_sell_signals:
            day_reasons[reason] = day_reasons.get(reason, 0) + 1
        for reason, count in sorted(day_reasons.items(), key=lambda x: -x[1])[:5]:
            print(f"  - {reason}: {count} 只")

print(f"\n{'='*70}")
print("卖出原因统计")
print(f"{'='*70}")
for reason, count in sorted(sell_reasons_count.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {count} 次")

# 分析具体股票的买卖情况
print(f"\n{'='*70}")
print("典型股票案例分析 (2025-01-02买入，2025-01-03卖出)")
print(f"{'='*70}")

# 找到2025-01-02买入，2025-01-03卖出的股票
if '2025-01-02' in fm.dates and '2025-01-03' in fm.dates:
    jan2_idx = fm.dates.index('2025-01-02')
    jan3_idx = fm.dates.index('2025-01-03')
    
    for n_idx, code in enumerate(fm.codes_str):
        if signals[jan2_idx, n_idx] == 1 and signals[jan3_idx, n_idx] == 2:
            # 获取数据
            close_jan2 = strategy.close[jan2_idx, n_idx]
            close_jan3 = strategy.close[jan3_idx, n_idx]
            ma10_jan2 = strategy.ma10[jan2_idx, n_idx]
            ma10_jan3 = strategy.ma10[jan3_idx, n_idx]
            ma20_jan2 = strategy.ma20[jan2_idx, n_idx]
            ma20_jan3 = strategy.ma20[jan3_idx, n_idx]
            reason = strategy.sell_reasons_matrix[jan3_idx, n_idx]
            
            print(f"\n  {code}:")
            print(f"    2025-01-02: 收盘价={close_jan2:.2f}, MA10={ma10_jan2:.2f}, MA20={ma20_jan2:.2f}")
            print(f"    2025-01-03: 收盘价={close_jan3:.2f}, MA10={ma10_jan3:.2f}, MA20={ma20_jan3:.2f}")
            print(f"    卖出原因: {reason}")
            
            if len([c for c, r in [(code, reason)]]) >= 5:  # 只显示前5只
                break

print(f"\n{'='*70}")
print("结论与建议")
print(f"{'='*70}")
print("""
根据卖出原因分析，可以判断策略是否过于敏感：

1. 如果主要是"跌破MA10/MA20"：
   - 说明趋势破坏条件太敏感
   - 建议：添加缓冲阈值，如跌破MA10超过2%才卖出

2. 如果主要是"乖离过大"：
   - 说明止盈条件太严格
   - 建议：提高乖离阈值或添加移动止盈

3. 如果两者都有：
   - 需要综合调整卖出条件
   - 建议添加最小持仓时间检查
""")
