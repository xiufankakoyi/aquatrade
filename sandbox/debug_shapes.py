"""
调试数组形状问题
"""
import sys
sys.path.insert(0, r'c:\Users\Liu\Desktop\projects\aquatrade')

import numpy as np
from core.strategies.user.main_wave_trend import MainWaveTrendStrategy
from data_svc.unified_data_manager import get_unified_manager

# 创建策略
strategy = MainWaveTrendStrategy()

# 加载数据
manager = get_unified_manager()
start_date = "2024-01-02"
end_date = "2024-01-10"  # 短周期便于调试

print("预加载数据...")
preloaded = manager.preload_to_memory(start_date=start_date, end_date=end_date)

stock_daily = preloaded.get('stock_daily')
if stock_daily is None or stock_daily.is_empty():
    print("❌ 没有股票数据")
    sys.exit(1)

print(f"stock_daily: {len(stock_daily)} 行")

# 获取交易日期和股票代码
trading_dates = sorted(stock_daily['trade_date'].unique().to_list())
stock_codes = sorted(stock_daily['stock_code'].unique().to_list())

T = len(trading_dates)
N = len(stock_codes)

print(f"T (交易日): {T}")
print(f"N (股票数): {N}")

# 构建价格矩阵
price_matrix = np.full((T, N, 4), np.nan, dtype=np.float32)

date_to_idx = {d: i for i, d in enumerate(trading_dates)}
code_to_idx = {c: i for i, c in enumerate(stock_codes)}

for row in stock_daily.iter_rows(named=True):
    date_idx = date_to_idx.get(row['trade_date'])
    code_idx = code_to_idx.get(row['stock_code'])
    if date_idx is not None and code_idx is not None:
        price_matrix[date_idx, code_idx, 0] = row.get('open', np.nan)
        price_matrix[date_idx, code_idx, 1] = row.get('high', np.nan)
        price_matrix[date_idx, code_idx, 2] = row.get('low', np.nan)
        price_matrix[date_idx, code_idx, 3] = row.get('close', np.nan)

print(f"\n价格矩阵形状: {price_matrix.shape}")

# 调用 prepare_data
print("\n调用 prepare_data...")
strategy.prepare_data(preloaded, trading_dates, stock_codes, price_matrix)

print(f"\n策略数据形状检查:")
print(f"  close: {strategy.close.shape}")
print(f"  ma5: {strategy.ma5.shape}")
print(f"  ma10: {strategy.ma10.shape}")
print(f"  ma20: {strategy.ma20.shape}")
print(f"  is_st: {strategy.is_st.shape if strategy.is_st is not None else None}")
print(f"  days_listed: {strategy.days_listed.shape if strategy.days_listed is not None else None}")
print(f"  total_mv: {strategy.total_mv.shape if strategy.total_mv is not None else None}")

# 手动调用 _detect_breakout 和 _detect_pullback 检查形状
print("\n检查 _detect_breakout 返回形状...")
breakout_signal = strategy._detect_breakout(strategy.close, strategy.high, strategy.ma20)
print(f"  breakout_signal: {breakout_signal.shape}")

print("\n检查 _detect_pullback 返回形状...")
pullback_signal = strategy._detect_pullback(strategy.close, strategy.low, strategy.ma5, strategy.ma10)
print(f"  pullback_signal: {pullback_signal.shape}")

# 检查所有用于买入信号的数组形状
print("\n买入信号各组件形状:")
close = strategy.close
ma5 = strategy.ma5
ma10 = strategy.ma10
ma20 = strategy.ma20

trend_bullish = (ma5 > ma10) & (ma10 > ma20)
print(f"  trend_bullish: {trend_bullish.shape}")

price_above_ma20 = close > ma20
print(f"  price_above_ma20: {price_above_ma20.shape}")

volume_ok = np.ones((T, N), dtype=bool)
if strategy.volume_ratio is not None:
    volume_ok = (strategy.volume_ratio >= strategy.config.volume_ratio_min) | ~np.isfinite(strategy.volume_ratio)
print(f"  volume_ok: {volume_ok.shape}")

bias = np.where(ma5 > 0, (close / ma5 - 1), np.nan)
print(f"  bias: {bias.shape}")

bias_ok_for_buy = (bias < strategy.config.bias_normal_max) | ~np.isfinite(bias)
print(f"  bias_ok_for_buy: {bias_ok_for_buy.shape}")

not_st = np.ones((T, N), dtype=bool)
if strategy.is_st is not None:
    not_st = (strategy.is_st == 0)
    print(f"  not_st (from is_st): {not_st.shape}")
    print(f"  is_st shape: {strategy.is_st.shape}")

listed_long_enough = np.ones((T, N), dtype=bool)
if strategy.days_listed is not None:
    listed_long_enough = (strategy.days_listed >= strategy.config.min_list_days) | ~np.isfinite(strategy.days_listed)
    print(f"  listed_long_enough (from days_listed): {listed_long_enough.shape}")
    print(f"  days_listed shape: {strategy.days_listed.shape}")

market_cap_ok = np.ones((T, N), dtype=bool)
if strategy.total_mv is not None:
    market_cap_ok = ((strategy.total_mv >= strategy.config.market_cap_min) & (strategy.total_mv <= strategy.config.market_cap_max)) | ~np.isfinite(strategy.total_mv)
    print(f"  market_cap_ok (from total_mv): {market_cap_ok.shape}")
    print(f"  total_mv shape: {strategy.total_mv.shape}")

print("\n尝试组合买入信号...")
try:
    buy_mask = (
        trend_bullish &
        price_above_ma20 &
        (breakout_signal | pullback_signal) &
        volume_ok &
        bias_ok_for_buy &
        not_st &
        listed_long_enough &
        market_cap_ok
    )
    print(f"✅ buy_mask 成功创建: {buy_mask.shape}")
except Exception as e:
    print(f"❌ 错误: {e}")
