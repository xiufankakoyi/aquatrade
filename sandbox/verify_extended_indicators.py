#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证扩展指标计算结果"""
import polars as pl
from pathlib import Path

DATA_PATH = Path("data/parquet_data/stock_daily_complete_indicators.parquet")

print("=" * 80)
print("📊 扩展指标验证报告")
print("=" * 80)

# 加载数据
df = pl.read_parquet(DATA_PATH)
print(f"\n📁 数据文件: {DATA_PATH}")
print(f"   总行数: {len(df):,}")
print(f"   股票数: {df['stock_code'].n_unique():,}")
print(f"   日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

# 定义新增指标
new_indicators = {
    # EMA指标
    'ema12': 'EMA 12日',
    'ema26': 'EMA 26日',
    'ema50': 'EMA 50日',
    'ema200': 'EMA 200日',
    # 技术指标补充
    'macd_golden_cross': 'MACD金叉',
    'macd_death_cross': 'MACD死叉',
    'mfi_14': 'MFI 14日',
    'volume_std_20d': '成交量标准差 20日',
    'bb_width_20': '布林带宽度',
    'atr_ratio_14_50': 'ATR比例 14/50',
    # 市场风险指标
    'beta_60d': 'Beta 60日',
    'beta_120d': 'Beta 120日',
    'beta_250d': 'Beta 250日',
    'alpha_60d': 'Alpha 60日(年化%)',
    'alpha_120d': 'Alpha 120日(年化%)',
    'alpha_250d': 'Alpha 250日(年化%)',
    'corr_60d': '相关系数 60日',
    'corr_120d': '相关系数 120日',
    'corr_250d': '相关系数 250日',
    'excess_ret_20d': '超额收益 20日',
    'ir_250d': '信息比率 250日',
    # 风险调整指标
    'sortino_250d': 'Sortino比率 250日',
    'calmar_250d': 'Calmar比率 250日',
    'var_95_250d': 'VaR 95% 250日',
    # 多窗口回撤
    'max_drawdown_60d': '最大回撤 60日',
    'max_drawdown_250d': '最大回撤 250日',
}

print("\n" + "=" * 80)
print("📋 新增指标验证")
print("=" * 80)

all_ok = True
for col, desc in new_indicators.items():
    if col in df.columns:
        null_count = df[col].null_count()
        null_pct = null_count / len(df) * 100
        status = "✅" if null_pct < 50 else "⚠️"
        print(f"{status} {col:20s} - {desc:25s} | 空值: {null_pct:5.1f}%")
    else:
        print(f"❌ {col:20s} - {desc:25s} | 列不存在!")
        all_ok = False

# 统计信息
print("\n" + "=" * 80)
print("📈 指标统计摘要")
print("=" * 80)

# 选择几个关键指标展示统计信息
key_indicators = ['beta_250d', 'alpha_250d', 'corr_250d', 'sortino_250d', 'mfi_14', 'bb_width_20']

for col in key_indicators:
    if col in df.columns:
        non_null = df[col].drop_nulls()
        if len(non_null) > 0:
            print(f"\n{col}:")
            print(f"   均值: {non_null.mean():.4f}")
            print(f"   标准差: {non_null.std():.4f}")
            print(f"   最小值: {non_null.min():.4f}")
            print(f"   最大值: {non_null.max():.4f}")
        else:
            print(f"\n{col}: 无有效数据")

# 样本数据展示
print("\n" + "=" * 80)
print("🔍 样本数据 (平安银行 000001)")
print("=" * 80)

sample = df.filter(pl.col("stock_code") == "000001").sort("trade_date").tail(5)
sample_cols = ['trade_date', 'close', 'ema12', 'ema26', 'beta_250d', 'alpha_250d', 'corr_250d', 'sortino_250d', 'mfi_14']
sample_cols = [c for c in sample_cols if c in sample.columns]
print(sample.select(sample_cols))

print("\n" + "=" * 80)
if all_ok:
    print("✅ 所有扩展指标验证通过!")
else:
    print("⚠️ 部分指标存在问题，请检查")
print("=" * 80)
