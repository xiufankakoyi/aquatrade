"""
诊断策略无买入信号的问题
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import numpy as np
from datetime import datetime

from config.config import Config
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


def diagnose_trend_strategy():
    """诊断 trend_follow_v1 策略为什么没有买入信号"""
    
    print("=" * 70)
    print("诊断 trend_follow_v1 策略")
    print("=" * 70)
    
    # 初始化数据查询
    data_query = OptimizedStockDataQuery(warmup=True)
    
    # 测试日期：2024-01-02（回测第一天）
    test_date = "20240102"
    previous_date = "20231229"  # 前一个交易日
    
    print(f"\n测试日期: {test_date}")
    print(f"前一交易日: {previous_date}")
    
    # 1. 获取股票池
    print("\n--- 步骤1: 获取股票池 ---")
    try:
        pool = data_query.get_stock_pool(previous_date, use_cache=True, filters={"min_mv": 0})
        if pool is None or pool.empty:
            print("❌ 股票池为空！")
            return
        print(f"✅ 股票池行数: {len(pool)}")
        print(f"   列: {list(pool.columns)}")
    except Exception as e:
        print(f"❌ 获取股票池失败: {e}")
        return
    
    # 2. 市值过滤
    print("\n--- 步骤2: 市值过滤 ---")
    market_cap_min = 50 * 10_000  # 50亿
    market_cap_max = 500 * 10_000  # 500亿
    
    print(f"   市值范围: {market_cap_min/10000:.0f}亿 - {market_cap_max/10000:.0f}亿")
    
    # 检查 total_mv 列
    if "total_mv" in pool.columns:
        print(f"   total_mv 统计: min={pool['total_mv'].min()/10000:.1f}亿, max={pool['total_mv'].max()/10000:.1f}亿, mean={pool['total_mv'].mean()/10000:.1f}亿")
        
        mv_mask = (pool["total_mv"] >= market_cap_min) & (pool["total_mv"] <= market_cap_max)
        mv_filtered = pool[mv_mask]
        print(f"   市值过滤后: {len(mv_filtered)} 只股票")
    else:
        print("   ⚠️ 缺少 total_mv 列")
        mv_filtered = pool
    
    # 3. ST过滤
    print("\n--- 步骤3: ST过滤 ---")
    if "is_st" in mv_filtered.columns:
        st_filtered = mv_filtered[mv_filtered["is_st"] == 0]
        print(f"   ST过滤后: {len(st_filtered)} 只股票")
    else:
        print("   ⚠️ 缺少 is_st 列")
        st_filtered = mv_filtered
    
    # 4. 检查关键列
    print("\n--- 步骤4: 检查关键列 ---")
    required_cols = ["stock_code", "close", "prev_close", "ma5", "ma10", "volume_ratio", "high", "total_mv"]
    for col in required_cols:
        if col in st_filtered.columns:
            non_null = st_filtered[col].notna().sum()
            print(f"   {col}: {non_null}/{len(st_filtered)} 非空")
        else:
            print(f"   {col}: ❌ 缺失")
    
    # 5. 逐步检查买入条件
    print("\n--- 步骤5: 逐步检查买入条件 ---")
    
    candidates = st_filtered.drop_duplicates(subset=["stock_code"]).copy()
    print(f"   去重后: {len(candidates)} 只股票")
    
    # 5.1 价格相对MA5的乖离
    print("\n   5.1 价格乖离 (close vs MA5):")
    candidates["close"] = pd.to_numeric(candidates["close"], errors="coerce")
    candidates["ma5"] = pd.to_numeric(candidates["ma5"], errors="coerce")
    
    price_ma_gap = (candidates["close"] / candidates["ma5"]) - 1
    print(f"       乖离统计: min={price_ma_gap.min():.2%}, max={price_ma_gap.max():.2%}, mean={price_ma_gap.mean():.2%}")
    
    price_gap_mask = (price_ma_gap >= 0.005) & (price_ma_gap <= 0.06)
    print(f"       满足 0.5%-6% 乖离: {price_gap_mask.sum()} 只")
    
    # 5.2 MA5 vs MA10 趋势强度
    print("\n   5.2 趋势强度 (MA5 vs MA10):")
    if "ma10" in candidates.columns:
        candidates["ma10"] = pd.to_numeric(candidates["ma10"], errors="coerce")
        ma_gap = (candidates["ma5"] / candidates["ma10"]) - 1
        print(f"       MA5/MA10-1 统计: min={ma_gap.min():.2%}, max={ma_gap.max():.2%}, mean={ma_gap.mean():.2%}")
        
        trend_mask = ma_gap >= 0.005
        print(f"       满足 MA5比MA10高0.5%: {trend_mask.sum()} 只")
    else:
        print("       ⚠️ 缺少 ma10 列")
        trend_mask = pd.Series(True, index=candidates.index)
    
    # 5.3 量比
    print("\n   5.3 量比条件:")
    if "volume_ratio" in candidates.columns:
        candidates["volume_ratio"] = pd.to_numeric(candidates["volume_ratio"], errors="coerce").fillna(0)
        print(f"       量比统计: min={candidates['volume_ratio'].min():.2f}, max={candidates['volume_ratio'].max():.2f}, mean={candidates['volume_ratio'].mean():.2f}")
        
        volume_mask = candidates["volume_ratio"] >= 1.2
        print(f"       满足量比>=1.2: {volume_mask.sum()} 只")
    else:
        print("       ⚠️ 缺少 volume_ratio 列")
        volume_mask = pd.Series(True, index=candidates.index)
    
    # 5.4 上影线
    print("\n   5.4 上影线条件:")
    if "high" in candidates.columns:
        candidates["high"] = pd.to_numeric(candidates["high"], errors="coerce")
        upper = (candidates["high"] - candidates["close"]) / candidates["close"].replace(0, pd.NA)
        upper_mask = upper <= 0.03
        upper_mask = upper_mask.fillna(False)
        print(f"       满足上影线<=3%: {upper_mask.sum()} 只")
    else:
        print("       ⚠️ 缺少 high 列")
        upper_mask = pd.Series(True, index=candidates.index)
    
    # 5.5 收盘价>=昨收
    print("\n   5.5 收盘价>=昨收:")
    candidates["prev_close"] = pd.to_numeric(candidates["prev_close"], errors="coerce")
    basic_price_mask = candidates["close"] >= candidates["prev_close"]
    print(f"       满足 close>=prev_close: {basic_price_mask.sum()} 只")
    
    # 6. 综合条件
    print("\n--- 步骤6: 综合条件 ---")
    final_mask = price_gap_mask & trend_mask & volume_mask & upper_mask & basic_price_mask
    final_candidates = candidates.loc[final_mask]
    
    print(f"   最终满足所有条件的股票: {len(final_candidates)} 只")
    
    if len(final_candidates) > 0:
        print("\n   前10只候选股票:")
        display_cols = ["stock_code", "close", "ma5", "ma10", "volume_ratio", "total_mv"]
        available_cols = [c for c in display_cols if c in final_candidates.columns]
        print(final_candidates[available_cols].head(10).to_string())
    else:
        print("\n   ❌ 没有股票满足所有买入条件！")
        
        # 分析哪个条件最严格
        print("\n   条件通过率分析:")
        total = len(candidates)
        print(f"   - 价格乖离 0.5%-6%: {price_gap_mask.sum()}/{total} ({price_gap_mask.sum()/total*100:.1f}%)")
        print(f"   - MA5>MA10+0.5%: {trend_mask.sum()}/{total} ({trend_mask.sum()/total*100:.1f}%)")
        print(f"   - 量比>=1.2: {volume_mask.sum()}/{total} ({volume_mask.sum()/total*100:.1f}%)")
        print(f"   - 上影线<=3%: {upper_mask.sum()}/{total} ({upper_mask.sum()/total*100:.1f}%)")
        print(f"   - 收盘>=昨收: {basic_price_mask.sum()}/{total} ({basic_price_mask.sum()/total*100:.1f}%)")


def diagnose_main_wave_strategy():
    """诊断 main_wave_trend 策略"""
    
    print("\n" + "=" * 70)
    print("诊断 main_wave_trend 策略")
    print("=" * 70)
    
    from core.strategies.user.main_wave_trend import MainWaveStrategy, MainWaveConfig
    
    # 初始化数据查询
    data_query = OptimizedStockDataQuery(warmup=True)
    
    # 获取交易日
    trading_dates = data_query.get_trading_dates()
    print(f"\n交易日范围: {trading_dates[0]} ~ {trading_dates[-1]}")
    
    # 测试日期
    test_date = "20240102"
    
    # 获取股票池
    pool = data_query.get_stock_pool(test_date, use_cache=True, filters={"min_mv": 0})
    if pool is None or pool.empty:
        print("❌ 股票池为空")
        return
    
    print(f"股票池行数: {len(pool)}")
    
    # 检查均线数据
    print("\n检查均线数据:")
    for col in ["ma5", "ma10", "ma20"]:
        if col in pool.columns:
            valid = pool[col].notna().sum()
            print(f"  {col}: {valid}/{len(pool)} 非空")
        else:
            print(f"  {col}: ❌ 缺失")


if __name__ == "__main__":
    diagnose_trend_strategy()
    # diagnose_main_wave_strategy()
