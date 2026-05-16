"""
股票涨跌与两会相关性分析 - 验证两会效应假设
============================================

验证假设：会前涨(>0)、会中跌(<0)、会后涨(>0)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from math import comb

# 读取数据
df = pd.read_csv(Path(__file__).parent / "lianghui_analysis_results.csv")

print("="*80)
print("两会效应验证：会前涨(>0)、会中跌(<0)、会后涨(>0)")
print("="*80)

# 准备数据
pre_data = df[df['时间段'].str.contains('两会前5日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会前收益'})
during_data = df[df['时间段'].str.contains('两会期间')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会中收益'})
post3_data = df[df['时间段'].str.contains('两会后3日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会后3日收益'})
post7_data = df[df['时间段'].str.contains('两会后7日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会后7日收益'})
post15_data = df[df['时间段'].str.contains('两会后15日')][['年份', '平均收益率(%)']].rename(columns={'平均收益率(%)': '会后15日收益'})

# 合并数据
merged = pre_data.merge(during_data, on='年份').merge(post3_data, on='年份').merge(post7_data, on='年份').merge(post15_data, on='年份')

print(f"\n样本数量: {len(merged)} 年 (2015-2025)")
print("-"*80)

def binom_test(k, n, p=0.5, alternative='greater'):
    """二项检验
    alternative: 'greater' 检验k是否显著大于np
                 'less' 检验k是否显著小于np
    """
    if alternative == 'greater':
        # 单侧检验: P(X >= k)
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(k, n+1))
    elif alternative == 'less':
        # 单侧检验: P(X <= k)
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(0, k+1))
    else:
        # 双侧检验
        p_value = 2 * min(
            sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(k, n+1)),
            sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(0, k+1))
        )
    return p_value

# 假设1: 会前收益 > 0 (会前涨)
print("\n【假设1】会前5日收益 > 0 (会前涨)")
print("-"*60)
h1_positive = (merged['会前收益'] > 0).sum()
h1_total = len(merged)
h1_mean = merged['会前收益'].mean()
print(f"  正收益年份: {h1_positive}/{h1_total} ({h1_positive/h1_total*100:.1f}%)")
print(f"  平均收益: {h1_mean:+.2f}%")
h1_pvalue = binom_test(h1_positive, h1_total, 0.5, 'greater')
print(f"  二项检验p值: {h1_pvalue:.4f}")
print(f"  结论: {'✓ 会前显著上涨' if h1_pvalue < 0.05 else '✗ 会前上涨不显著'}")

# 假设2: 会中收益 < 0 (会中跌)
print("\n【假设2】会中收益 < 0 (会中跌)")
print("-"*60)
h2_negative = (merged['会中收益'] < 0).sum()
h2_mean = merged['会中收益'].mean()
print(f"  负收益年份: {h2_negative}/{h1_total} ({h2_negative/h1_total*100:.1f}%)")
print(f"  平均收益: {h2_mean:+.2f}%")
h2_pvalue = binom_test(h2_negative, h1_total, 0.5, 'greater')
print(f"  二项检验p值: {h2_pvalue:.4f}")
print(f"  结论: {'✓ 会中显著下跌' if h2_pvalue < 0.05 else '✗ 会中下跌不显著'}")

# 假设3: 会后收益 > 0 (会后涨)
print("\n【假设3】会后收益 > 0 (会后涨)")
print("-"*60)

for period_name, col_name in [('会后3日', '会后3日收益'), ('会后7日', '会后7日收益'), ('会后15日', '会后15日收益')]:
    h3_positive = (merged[col_name] > 0).sum()
    h3_mean = merged[col_name].mean()
    h3_pvalue = binom_test(h3_positive, h1_total, 0.5, 'greater')
    
    print(f"\n  {period_name}:")
    print(f"    正收益年份: {h3_positive}/{h1_total} ({h3_positive/h1_total*100:.1f}%)")
    print(f"    平均收益: {h3_mean:+.2f}%")
    print(f"    二项检验p值: {h3_pvalue:.4f}")
    print(f"    结论: {'✓ 会后显著上涨' if h3_pvalue < 0.05 else '✗ 会后上涨不显著'}")

# 综合检验: 三个条件同时满足的年份
print("\n\n【综合检验】三个条件同时满足的年份")
print("-"*60)
print("条件: 会前>0 且 会中<0 且 会后15日>0")

merged['会前>0'] = merged['会前收益'] > 0
merged['会中<0'] = merged['会中收益'] < 0
merged['会后15日>0'] = merged['会后15日收益'] > 0

merged['三条件满足'] = merged['会前>0'] & merged['会中<0'] & merged['会后15日>0']

three_conditions_met = merged['三条件满足'].sum()
print(f"\n三条件同时满足的年份: {three_conditions_met}/{h1_total} ({three_conditions_met/h1_total*100:.1f}%)")

# 检验三条件同时满足的比例是否显著高于随机(12.5% = 0.5^3)
random_prob = 0.125
h_combined_pvalue = binom_test(three_conditions_met, h1_total, random_prob, 'greater')
print(f"二项检验p值(对比随机12.5%): {h_combined_pvalue:.4f}")
print(f"结论: {'✓ 两会效应显著存在' if h_combined_pvalue < 0.05 else '✗ 两会效应不显著'}")

# 导出CSV - 年度明细
print("\n\n导出CSV文件...")

# 1. 年度明细表
detail_df = merged[['年份', '会前收益', '会中收益', '会后3日收益', '会后7日收益', '会后15日收益', 
                     '会前>0', '会中<0', '会后15日>0', '三条件满足']].copy()
detail_df.columns = ['年份', '会前5日收益', '两会期间收益', '会后3日收益', '会后7日收益', '会后15日收益',
                     '会前涨', '会中跌', '会后涨', '三条件满足']

# 转换布尔值为中文
detail_df['会前涨'] = detail_df['会前涨'].map({True: '是', False: '否'})
detail_df['会中跌'] = detail_df['会中跌'].map({True: '是', False: '否'})
detail_df['会后涨'] = detail_df['会后涨'].map({True: '是', False: '否'})
detail_df['三条件满足'] = detail_df['三条件满足'].map({True: '是', False: '否'})

detail_csv_path = Path(__file__).parent / "lianghui_year_detail.csv"
detail_df.to_csv(detail_csv_path, index=False, encoding='utf-8-sig')
print(f"✓ 年度明细表已保存: {detail_csv_path}")

# 2. 假设检验结果表
hypothesis_results = [
    {'假设': '会前涨 (收益>0)', '满足年份': f"{h1_positive}/{h1_total}", '比例': f"{h1_positive/h1_total*100:.1f}%", 
     '平均收益': f"{h1_mean:+.2f}%", 'p值': f"{h1_pvalue:.4f}", '结论': '显著' if h1_pvalue < 0.05 else '不显著'},
    {'假设': '会中跌 (收益<0)', '满足年份': f"{h2_negative}/{h1_total}", '比例': f"{h2_negative/h1_total*100:.1f}%", 
     '平均收益': f"{h2_mean:+.2f}%", 'p值': f"{h2_pvalue:.4f}", '结论': '显著' if h2_pvalue < 0.05 else '不显著'},
    {'假设': '会后3日涨 (收益>0)', '满足年份': f"{(merged['会后3日收益']>0).sum()}/{h1_total}", 
     '比例': f"{(merged['会后3日收益']>0).mean()*100:.1f}%", '平均收益': f"{merged['会后3日收益'].mean():+.2f}%", 
     'p值': f"{binom_test((merged['会后3日收益']>0).sum(), h1_total, 0.5, 'greater'):.4f}", 
     '结论': '显著' if binom_test((merged['会后3日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '不显著'},
    {'假设': '会后7日涨 (收益>0)', '满足年份': f"{(merged['会后7日收益']>0).sum()}/{h1_total}", 
     '比例': f"{(merged['会后7日收益']>0).mean()*100:.1f}%", '平均收益': f"{merged['会后7日收益'].mean():+.2f}%", 
     'p值': f"{binom_test((merged['会后7日收益']>0).sum(), h1_total, 0.5, 'greater'):.4f}", 
     '结论': '显著' if binom_test((merged['会后7日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '不显著'},
    {'假设': '会后15日涨 (收益>0)', '满足年份': f"{(merged['会后15日收益']>0).sum()}/{h1_total}", 
     '比例': f"{(merged['会后15日收益']>0).mean()*100:.1f}%", '平均收益': f"{merged['会后15日收益'].mean():+.2f}%", 
     'p值': f"{binom_test((merged['会后15日收益']>0).sum(), h1_total, 0.5, 'greater'):.4f}", 
     '结论': '显著' if binom_test((merged['会后15日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '不显著'},
    {'假设': '三条件同时满足', '满足年份': f"{three_conditions_met}/{h1_total}", 
     '比例': f"{three_conditions_met/h1_total*100:.1f}%", '平均收益': '-', 
     'p值': f"{h_combined_pvalue:.4f}", '结论': '显著' if h_combined_pvalue < 0.05 else '不显著'},
]

hypothesis_df = pd.DataFrame(hypothesis_results)
hypothesis_csv_path = Path(__file__).parent / "lianghui_hypothesis_test.csv"
hypothesis_df.to_csv(hypothesis_csv_path, index=False, encoding='utf-8-sig')
print(f"✓ 假设检验结果表已保存: {hypothesis_csv_path}")

# 3. 策略对比表
strategy_returns = []
for _, row in merged.iterrows():
    strategy_return = row['会前收益'] + row['会后15日收益']  # 会前建仓 + 会后建仓，会中空仓
    buy_hold_return = row['会前收益'] + row['会中收益'] + row['会后15日收益']  # 全程持有
    
    strategy_returns.append({
        '年份': int(row['年份']),
        '会前5日收益': row['会前收益'],
        '两会期间收益': row['会中收益'],
        '会后15日收益': row['会后15日收益'],
        '择时策略收益(会前+会后)': strategy_return,
        '买入持有收益(全程)': buy_hold_return,
        '超额收益': strategy_return - buy_hold_return
    })

strategy_df = pd.DataFrame(strategy_returns)
strategy_csv_path = Path(__file__).parent / "lianghui_strategy_comparison.csv"
strategy_df.to_csv(strategy_csv_path, index=False, encoding='utf-8-sig')
print(f"✓ 策略对比表已保存: {strategy_csv_path}")

# 打印年度明细
print("\n\n【年度明细】")
print("-"*80)
print(detail_df.to_string(index=False))

# 打印策略对比
print("\n\n【策略对比】")
print("-"*80)
print(strategy_df.to_string(index=False))

print(f"\n\n策略统计:")
print(f"  择时策略(会前+会后)平均收益: {strategy_df['择时策略收益(会前+会后)'].mean():+.2f}%")
print(f"  买入持有(全程)平均收益: {strategy_df['买入持有收益(全程)'].mean():+.2f}%")
print(f"  平均超额收益: {strategy_df['超额收益'].mean():+.2f}%")

# 最终结论
print("\n\n" + "="*80)
print("【最终结论】")
print("="*80)

conclusion = f"""
1. 会前效应验证:
   {'✓' if h1_pvalue < 0.05 else '✗'} 会前5日显著上涨 (p={h1_pvalue:.4f})
   - 正收益年份: {h1_positive}/{h1_total} ({h1_positive/h1_total*100:.1f}%)
   
2. 会中效应验证:
   {'✓' if h2_pvalue < 0.05 else '✗'} 会中显著下跌 (p={h2_pvalue:.4f})
   - 负收益年份: {h2_negative}/{h1_total} ({h2_negative/h1_total*100:.1f}%)
   
3. 会后效应验证:
   {'✓' if binom_test((merged['会后3日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '✗'} 会后3日显著上涨
   {'✓' if binom_test((merged['会后7日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '✗'} 会后7日显著上涨  
   {'✓' if binom_test((merged['会后15日收益']>0).sum(), h1_total, 0.5, 'greater') < 0.05 else '✗'} 会后15日显著上涨
   
4. 综合两会效应:
   {'✓' if h_combined_pvalue < 0.05 else '✗'} 三条件同时满足比例显著高于随机 (p={h_combined_pvalue:.4f})
   - 满足年份: {three_conditions_met}/{h1_total} ({three_conditions_met/h1_total*100:.1f}%)

5. 策略效果:
   - 择时策略平均收益: {strategy_df['择时策略收益(会前+会后)'].mean():+.2f}%
   - 买入持有平均收益: {strategy_df['买入持有收益(全程)'].mean():+.2f}%
   - 超额收益: {strategy_df['超额收益'].mean():+.2f}%
"""

print(conclusion)

print("\n\n已导出3个CSV文件到 sandbox 目录:")
print("  1. lianghui_year_detail.csv - 年度明细数据")
print("  2. lianghui_hypothesis_test.csv - 假设检验结果")
print("  3. lianghui_strategy_comparison.csv - 策略对比数据")
