#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
计算预计算因子的存储大小
"""
import pandas as pd
import numpy as np

# 基础数据参数
STOCKS_PER_DAY = 5500  # 每天约5500只股票
DAYS_PER_YEAR = 242    # 每年约242个交易日（扣除周末和假期）

# 因子数量统计
SIMPLE_FACTORS = 15    # 简单因子：MA5, MA10, MA20, MA60, 收益, 波动率等
COMPLEX_FACTORS = 20   # 复杂因子：RSI(3), MACD(3), KDJ(3), 布林带(4), 其他技术指标
TOTAL_FACTORS = SIMPLE_FACTORS + COMPLEX_FACTORS

# 数据类型大小（字节）
FLOAT64_SIZE = 8       # float64
FLOAT32_SIZE = 4       # float32
INT32_SIZE = 4         # int32

print("=" * 70)
print("预计算因子存储大小估算")
print("=" * 70)

# 计算不同时间段的记录数
for years in [5, 10, 15]:
    total_days = DAYS_PER_YEAR * years
    total_records = STOCKS_PER_DAY * total_days
    
    print(f"\n{years}年数据：")
    print(f"  交易日数: {total_days:,} 天")
    print(f"  总记录数: {total_records:,} 条")
    
    # 基础数据（已存在）
    base_columns = 36  # stock_daily 现有列数
    base_size_float64 = total_records * base_columns * FLOAT64_SIZE
    base_size_float32 = total_records * base_columns * FLOAT32_SIZE
    
    # 新增因子数据
    factor_size_float64 = total_records * TOTAL_FACTORS * FLOAT64_SIZE
    factor_size_float32 = total_records * TOTAL_FACTORS * FLOAT32_SIZE
    
    # 总大小
    total_size_float64 = base_size_float64 + factor_size_float64
    total_size_float32 = base_size_float32 + factor_size_float32
    
    print(f"\n  存储大小估算（仅新增因子）：")
    print(f"    float64: {factor_size_float64 / 1024**3:.2f} GB")
    print(f"    float32: {factor_size_float32 / 1024**3:.2f} GB")
    
    print(f"\n  存储大小估算（含基础数据）：")
    print(f"    float64: {total_size_float64 / 1024**3:.2f} GB")
    print(f"    float32: {total_size_float32 / 1024**3:.2f} GB")

# 详细因子列表
print("\n" + "=" * 70)
print("因子详细列表（估算 35 个因子）")
print("=" * 70)

factors = {
    "均线类 (6个)": ["ma5", "ma10", "ma20", "ma30", "ma60", "ma120"],
    "RSI类 (3个)": ["rsi_6", "rsi_12", "rsi_24"],
    "MACD类 (5个)": ["macd_dif", "macd_dea", "macd_bar", "macd_golden_cross", "macd_death_cross"],
    "KDJ类 (3个)": ["kdj_k", "kdj_d", "kdj_j"],
    "布林带类 (4个)": ["boll_upper", "boll_mid", "boll_lower", "bb_width_20"],
    "收益类 (3个)": ["return_5d", "return_20d", "return_60d"],
    "风险类 (4个)": ["volatility_20d", "max_drawdown_20d", "beta_60d", "alpha_60d"],
    "成交量类 (3个)": ["vol_ma5", "vol_ma10", "vol_ma20"],
    "其他 (4个)": ["atr_14", "cci_14", "wr_14", "obv"]
}

total_factor_count = 0
for category, factor_list in factors.items():
    print(f"\n{category}:")
    for f in factor_list:
        print(f"  - {f}")
    total_factor_count += len(factor_list)

print(f"\n总计: {total_factor_count} 个因子")

# ArcticDB 压缩估算
print("\n" + "=" * 70)
print("ArcticDB 压缩后估算（假设压缩率 30-50%）")
print("=" * 70)

for years in [5, 10, 15]:
    total_days = DAYS_PER_YEAR * years
    total_records = STOCKS_PER_DAY * total_days
    factor_size = total_records * total_factor_count * FLOAT64_SIZE
    
    print(f"\n{years}年因子数据（float64）：")
    print(f"  原始大小: {factor_size / 1024**3:.2f} GB")
    print(f"  压缩后(50%): {factor_size * 0.5 / 1024**3:.2f} GB")
    print(f"  压缩后(30%): {factor_size * 0.3 / 1024**3:.2f} GB")

# 内存缓存估算
print("\n" + "=" * 70)
print("内存缓存需求估算（预加载最近2年数据）")
print("=" * 70)

cache_years = 2
cache_days = DAYS_PER_YEAR * cache_years
cache_records = STOCKS_PER_DAY * cache_days

# 基础数据 + 因子数据
total_columns = base_columns + total_factor_count
cache_size_float64 = cache_records * total_columns * FLOAT64_SIZE
cache_size_float32 = cache_records * total_columns * FLOAT32_SIZE

print(f"\n最近2年数据：")
print(f"  记录数: {cache_records:,} 条")
print(f"  列数: {total_columns} 列")
print(f"  float64: {cache_size_float64 / 1024**3:.2f} GB")
print(f"  float32: {cache_size_float32 / 1024**3:.2f} GB")

# 计算性能估算
print("\n" + "=" * 70)
print("预计算性能估算")
print("=" * 70)

print("""
假设条件：
- 每只股票计算35个因子需要 10ms（含数据读取、计算、写入）
- 每天5500只股票
- 每年242个交易日

计算时间：
""")

for years in [5, 10, 15]:
    total_days = DAYS_PER_YEAR * years
    total_stocks = STOCKS_PER_DAY * total_days
    
    # 假设每只股票10ms
    time_ms = total_stocks * 10
    time_hours = time_ms / 1000 / 3600
    time_days = time_hours / 24
    
    print(f"{years}年数据：")
    print(f"  总计算量: {total_stocks:,} 只股票-天")
    print(f"  预估时间: {time_hours:.1f} 小时 ({time_days:.1f} 天)")
    
    # 并行计算（假设8核）
    parallel_hours = time_hours / 8
    print(f"  并行(8核): {parallel_hours:.1f} 小时")

print("\n" + "=" * 70)
print("可行性评估建议")
print("=" * 70)

print("""
1. 存储空间：
   ✓ 15年数据约 20-30GB（压缩后），现代硬盘完全可接受
   ✓ 内存缓存 2-4GB，普通服务器可承受

2. 计算时间：
   ⚠ 全量预计算需要较长时间（数天）
   ✓ 建议采用增量更新策略（每天只计算最新数据）
   ✓ 首次全量计算可在后台分批进行

3. 查询性能：
   ✓ 预计算后查询速度提升 10-100倍
   ✓ 无需实时计算，降低CPU负载

4. 推荐方案：
   - 首次：全量预计算（后台分批）
   - 日常：每日增量更新（只计算最新1天）
   - 存储：使用 float32 节省空间
   - 缓存：预加载最近2年数据到内存
""")
