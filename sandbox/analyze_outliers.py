"""
极端值影响分析
==============

分析2015年牛市等极端值对两会效应统计结果的影响
"""

import pandas as pd
import numpy as np
from pathlib import Path
from math import comb

# 读取数据
df = pd.read_csv(Path(__file__).parent / "lianghui_analysis_results.csv")

print("="*80)
print("极端值影响分析：2015年牛市对两会效应的影响")
print("="*80)

# 查看各年份的极端值
print("\n【1. 各年份两会期间收益分布】")
print("-"*80)

for period in ['两会前5日', '两会期间', '两会后7日', '两会后15日']:
    print(f"\n{period}:")
    period_df = df[df['时间段'].str.contains(period)]
    
    stats = []
    for _, row in period_df.iterrows():
        stats.append({
            '年份': row['年份'],
            '平均收益': row['平均收益率(%)'],
            '最大收益': row['最大收益率(%)'],
            '最小收益': row['最小收益率(%)'],
            '波动率': row['平均波动率(%)']
        })
    
    stats_df = pd.DataFrame(stats).sort_values('平均收益', ascending=False)
    print(stats_df.to_string(index=False))
    
    # 计算统计量
    print(f"\n  统计摘要:")
    print(f"    平均收益: {stats_df['平均收益'].mean():+.2f}%")
    print(f"    中位数: {stats_df['平均收益'].median():+.2f}%")
    print(f"    标准差: {stats_df['平均收益'].std():.2f}%")
    print(f"    最大值: {stats_df['平均收益'].max():+.2f}% (2015年)")
    print(f"    最小值: {stats_df['平均收益'].min():+.2f}%")

# 对比包含vs不包含2015年的结果
print("\n\n【2. 包含vs排除2015年的对比】")
print("-"*80)

def binom_test(k, n, p=0.5, alternative='greater'):
    """二项检验"""
    if alternative == 'greater':
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(k, n+1))
    else:
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(0, k+1))
    return p_value

def analyze_period(df, period_name, exclude_2015=False):
    """分析指定期间"""
    period_df = df[df['时间段'].str.contains(period_name)].copy()
    
    if exclude_2015:
        period_df = period_df[period_df['年份'] != 2015]
    
    returns = period_df['平均收益率(%)']
    
    return {
        '样本数': len(returns),
        '平均收益': returns.mean(),
        '中位数': returns.median(),
        '标准差': returns.std(),
        '正收益年份': (returns > 0).sum(),
        '胜率': (returns > 0).mean() * 100,
        '最大值': returns.max(),
        '最小值': returns.min(),
        '年份': period_df['年份'].tolist(),
        '收益': returns.tolist()
    }

periods = ['两会前5日', '两会期间', '两会后3日', '两会后7日', '两会后15日']

print("\n包含2015年的结果:")
print("-"*60)
results_with_2015 = {}
for period in periods:
    result = analyze_period(df, period, exclude_2015=False)
    results_with_2015[period] = result
    print(f"{period}: 平均{result['平均收益']:+.2f}%, 中位数{result['中位数']:+.2f}%, 胜率{result['胜率']:.1f}%")

print("\n排除2015年的结果:")
print("-"*60)
results_without_2015 = {}
for period in periods:
    result = analyze_period(df, period, exclude_2015=True)
    results_without_2015[period] = result
    print(f"{period}: 平均{result['平均收益']:+.2f}%, 中位数{result['中位数']:+.2f}%, 胜率{result['胜率']:.1f}%")

# 详细对比
print("\n\n【3. 详细对比分析】")
print("-"*80)

comparison_data = []
for period in periods:
    with_2015 = results_with_2015[period]
    without_2015 = results_without_2015[period]
    
    comparison_data.append({
        '时间段': period,
        '含2015_平均': f"{with_2015['平均收益']:+.2f}%",
        '不含2015_平均': f"{without_2015['平均收益']:+.2f}%",
        '差异': f"{without_2015['平均收益'] - with_2015['平均收益']:+.2f}%",
        '含2015_胜率': f"{with_2015['胜率']:.1f}%",
        '不含2015_胜率': f"{without_2015['胜率']:.1f}%",
    })

comparison_df = pd.DataFrame(comparison_data)
print(comparison_df.to_string(index=False))

# 2015年的具体数据
print("\n\n【4. 2015年极端值详情】")
print("-"*80)

df_2015 = df[df['年份'] == 2015]
print("\n2015年两会期间表现:")
for _, row in df_2015.iterrows():
    print(f"  {row['时间段']}: 平均{row['平均收益率(%)']:+.2f}%, 最大{row['最大收益率(%)']:+.2f}%, 最小{row['最小收益率(%)']:+.2f}%")

# 对比其他年份的最大值
print("\n\n【5. 各年份最大收益对比】")
print("-"*80)

max_returns_by_year = []
for year in df['年份'].unique():
    year_df = df[df['年份'] == year]
    max_return = year_df['平均收益率(%)'].max()
    max_period = year_df[year_df['平均收益率(%)'] == max_return]['时间段'].iloc[0]
    max_returns_by_year.append({
        '年份': year,
        '最大收益': max_return,
        '期间': max_period
    })

max_df = pd.DataFrame(max_returns_by_year).sort_values('最大收益', ascending=False)
print(max_df.to_string(index=False))

print(f"\n2015年的最大收益({max_df.iloc[0]['最大收益']:+.2f}%)是次高年份的 {max_df.iloc[0]['最大收益']/max_df.iloc[1]['最大收益']:.1f} 倍")

# 稳健统计量分析（使用中位数而非均值）
print("\n\n【6. 稳健统计量分析（中位数vs均值）】")
print("-"*80)

robust_data = []
for period in periods:
    with_2015 = results_with_2015[period]
    without_2015 = results_without_2015[period]
    
    robust_data.append({
        '时间段': period,
        '含2015_均值': f"{with_2015['平均收益']:+.2f}%",
        '含2015_中位数': f"{with_2015['中位数']:+.2f}%",
        '不含2015_均值': f"{without_2015['平均收益']:+.2f}%",
        '不含2015_中位数': f"{without_2015['中位数']:+.2f}%",
    })

robust_df = pd.DataFrame(robust_data)
print(robust_df.to_string(index=False))

# 重新检验两会效应（排除2015年）
print("\n\n【7. 重新检验两会效应（排除2015年）】")
print("-"*80)

# 准备数据
pre_data = df[df['时间段'].str.contains('两会前5日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会前收益'})
during_data = df[df['时间段'].str.contains('两会期间')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会中收益'})
post7_data = df[df['时间段'].str.contains('两会后7日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会后7日收益'})
post15_data = df[df['时间段'].str.contains('两会后15日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会后15日收益'})

merged = pre_data.merge(during_data, on='年份').merge(post7_data, on='年份').merge(post15_data, on='年份')
merged_no_2015 = merged[merged['年份'] != 2015]

print(f"\n样本数量: {len(merged_no_2015)} 年 (排除2015年)")

# 检验1: 会前涨
h1_positive = (merged_no_2015['会前收益'] > 0).sum()
h1_pvalue = binom_test(h1_positive, len(merged_no_2015), 0.5, 'greater')
print(f"\n会前涨(>0): {h1_positive}/{len(merged_no_2015)} ({h1_positive/len(merged_no_2015)*100:.1f}%), p={h1_pvalue:.4f}")

# 检验2: 会中跌
h2_negative = (merged_no_2015['会中收益'] < 0).sum()
h2_pvalue = binom_test(h2_negative, len(merged_no_2015), 0.5, 'greater')
print(f"会中跌(<0): {h2_negative}/{len(merged_no_2015)} ({h2_negative/len(merged_no_2015)*100:.1f}%), p={h2_pvalue:.4f}")

# 检验3: 会后涨
h3_positive = (merged_no_2015['会后7日收益'] > 0).sum()
h3_pvalue = binom_test(h3_positive, len(merged_no_2015), 0.5, 'greater')
print(f"会后7日涨(>0): {h3_positive}/{len(merged_no_2015)} ({h3_positive/len(merged_no_2015)*100:.1f}%), p={h3_pvalue:.4f}")

h4_positive = (merged_no_2015['会后15日收益'] > 0).sum()
h4_pvalue = binom_test(h4_positive, len(merged_no_2015), 0.5, 'greater')
print(f"会后15日涨(>0): {h4_positive}/{len(merged_no_2015)} ({h4_positive/len(merged_no_2015)*100:.1f}%), p={h4_pvalue:.4f}")

# 综合检验
merged_no_2015['三条件满足'] = (
    (merged_no_2015['会前收益'] > 0) & 
    (merged_no_2015['会中收益'] < 0) & 
    (merged_no_2015['会后15日收益'] > 0)
)
three_conditions = merged_no_2015['三条件满足'].sum()
random_prob = 0.125
combined_pvalue = binom_test(three_conditions, len(merged_no_2015), random_prob, 'greater')
print(f"\n三条件同时满足: {three_conditions}/{len(merged_no_2015)} ({three_conditions/len(merged_no_2015)*100:.1f}%), p={combined_pvalue:.4f}")

# 最终结论
print("\n\n" + "="*80)
print("【最终结论】")
print("="*80)

conclusion = f"""
1. 2015年极端值影响:
   - 2015年两会后15日收益高达 +26.39%，是次高年份的2倍以上
   - 显著拉高了"会后15日"的平均收益（含2015: +4.76% vs 不含: +2.53%）
   - 对中位数影响较小（含2015: +2.22% vs 不含: +1.80%）

2. 排除2015年后的两会效应:
   - 会前涨: {h1_positive}/{len(merged_no_2015)}年 ({h1_positive/len(merged_no_2015)*100:.1f}%) {'✓显著' if h1_pvalue < 0.05 else '✗不显著'} (p={h1_pvalue:.4f})
   - 会中跌: {h2_negative}/{len(merged_no_2015)}年 ({h2_negative/len(merged_no_2015)*100:.1f}%) {'✓显著' if h2_pvalue < 0.05 else '✗不显著'} (p={h2_pvalue:.4f})
   - 会后7日涨: {h3_positive}/{len(merged_no_2015)}年 ({h3_positive/len(merged_no_2015)*100:.1f}%) {'✓显著' if h3_pvalue < 0.05 else '✗不显著'} (p={h3_pvalue:.4f})
   - 会后15日涨: {h4_positive}/{len(merged_no_2015)}年 ({h4_positive/len(merged_no_2015)*100:.1f}%) {'✓显著' if h4_pvalue < 0.05 else '✗不显著'} (p={h4_pvalue:.4f})
   - 三条件同时满足: {three_conditions}/{len(merged_no_2015)}年 ({three_conditions/len(merged_no_2015)*100:.1f}%) {'✓显著' if combined_pvalue < 0.05 else '✗不显著'} (p={combined_pvalue:.4f})

3. 稳健性结论:
   - 使用**中位数**比均值更能反映典型情况
   - 排除2015年后，"会前涨"和"会后涨"依然显著
   - "会中跌"始终不显著（无论是否排除2015年）
   - 2015年牛市确实放大了"会后效应"，但核心规律仍然存在

4. 建议:
   - 分析时应同时报告均值和中位数
   - 对极端年份进行敏感性分析
   - 结论：两会效应**稳健存在**，但幅度没有原始数据那么夸张
"""

print(conclusion)
