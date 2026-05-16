"""
两会期间行业板块轮动分析
==========================

验证：会前预期→会中轮动→会后政策兑现的板块轮动规律
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

# 读取行业详细数据
df = pd.read_csv(Path(__file__).parent / "lianghui_industry_detail.csv")

print("="*80)
print("两会期间行业板块轮动分析")
print("="*80)

# 定义各期间
PERIODS = ['两会前5日', '两会期间', '两会后3日', '两会后7日', '两会后15日']


def get_top_sectors_by_year(df, year, period, top_n=5):
    """获取指定年份和期间的领涨板块"""
    period_df = df[(df['year'] == year) & (df['period'] == period)]
    if period_df.empty:
        return []
    
    # 按平均收益排序
    top_df = period_df.nlargest(top_n, 'avg_return')
    return top_df['industry'].tolist()


def get_sector_return(df, year, period, sector):
    """获取指定板块在指定期间的收益"""
    sector_df = df[(df['year'] == year) & (df['period'] == period) & (df['industry'] == sector)]
    if sector_df.empty:
        return None
    return sector_df.iloc[0]['avg_return']


def calculate_sector_stability(df, sector, period):
    """计算板块在指定期间的稳定性（胜率）"""
    sector_df = df[(df['period'] == period) & (df['industry'] == sector)]
    if len(sector_df) < 3:
        return None, None
    
    positive_years = (sector_df['avg_return'] > 0).sum()
    total_years = len(sector_df)
    win_rate = positive_years / total_years
    avg_return = sector_df['avg_return'].mean()
    
    return win_rate, avg_return


# 分析1: 各年份板块轮动情况
print("\n【1. 各年份板块轮动分析】")
print("-"*80)

years = sorted(df['year'].unique(), reverse=True)
rotation_analysis = []

for year in years:
    print(f"\n{year}年:")
    
    # 获取各期间领涨板块
    pre_sectors = get_top_sectors_by_year(df, year, '两会前5日', 3)
    during_sectors = get_top_sectors_by_year(df, year, '两会期间', 3)
    post3_sectors = get_top_sectors_by_year(df, year, '两会后3日', 3)
    post7_sectors = get_top_sectors_by_year(df, year, '两会后7日', 3)
    post15_sectors = get_top_sectors_by_year(df, year, '两会后15日', 3)
    
    print(f"  会前领涨: {' → '.join(pre_sectors) if pre_sectors else 'N/A'}")
    print(f"  会中领涨: {' → '.join(during_sectors) if during_sectors else 'N/A'}")
    print(f"  会后3日: {' → '.join(post3_sectors) if post3_sectors else 'N/A'}")
    print(f"  会后7日: {' → '.join(post7_sectors) if post7_sectors else 'N/A'}")
    print(f"  会后15日: {' → '.join(post15_sectors) if post15_sectors else 'N/A'}")
    
    # 计算轮动强度（相邻期间板块重叠度）
    def calc_overlap(list1, list2):
        if not list1 or not list2:
            return 0
        return len(set(list1) & set(list2)) / max(len(list1), len(list2))
    
    pre_to_during = calc_overlap(pre_sectors, during_sectors)
    during_to_post3 = calc_overlap(during_sectors, post3_sectors)
    post3_to_post7 = calc_overlap(post3_sectors, post7_sectors)
    post7_to_post15 = calc_overlap(post7_sectors, post15_sectors)
    
    print(f"  轮动强度: 会前→会中 {pre_to_during*100:.0f}% | 会中→会后3日 {during_to_post3*100:.0f}% | "
          f"会后3→7日 {post3_to_post7*100:.0f}% | 会后7→15日 {post7_to_post15*100:.0f}%")
    
    rotation_analysis.append({
        'year': year,
        'pre_sectors': pre_sectors,
        'during_sectors': during_sectors,
        'post7_sectors': post7_sectors,
        'pre_to_during': pre_to_during,
        'during_to_post': during_to_post3,
    })


# 分析2: 板块持续性分析
print("\n\n【2. 板块持续性分析（哪些板块能跨期间持续强势）】")
print("-"*80)

# 统计各板块在不同期间的持续性
sector_persistence = defaultdict(lambda: defaultdict(int))

for year in years:
    pre_sectors = get_top_sectors_by_year(df, year, '两会前5日', 5)
    during_sectors = get_top_sectors_by_year(df, year, '两会期间', 5)
    post7_sectors = get_top_sectors_by_year(df, year, '两会后7日', 5)
    post15_sectors = get_top_sectors_by_year(df, year, '两会后15日', 5)
    
    # 统计板块出现次数
    for s in pre_sectors:
        sector_persistence[s]['pre'] += 1
    for s in during_sectors:
        sector_persistence[s]['during'] += 1
    for s in post7_sectors:
        sector_persistence[s]['post7'] += 1
    for s in post15_sectors:
        sector_persistence[s]['post15'] += 1

# 找出跨期间持续的板块
print("\n跨期间持续强势的板块（至少在2个期间进入top5）:")
persistent_sectors = []
for sector, counts in sector_persistence.items():
    total = sum(counts.values())
    if total >= 4:  # 至少4次出现
        persistent_sectors.append({
            'sector': sector,
            'total': total,
            'pre': counts['pre'],
            'during': counts['during'],
            'post7': counts['post7'],
            'post15': counts['post15']
        })

persistent_df = pd.DataFrame(persistent_sectors).sort_values('total', ascending=False)
print(persistent_df.to_string(index=False))


# 分析3: 板块轮动规律验证
print("\n\n【3. 板块轮动规律验证】")
print("-"*80)

# 统计轮动强度
rotation_df = pd.DataFrame(rotation_analysis)
print(f"\n平均轮动强度:")
print(f"  会前→会中重叠度: {rotation_df['pre_to_during'].mean()*100:.1f}%")
print(f"  会中→会后重叠度: {rotation_df['during_to_post'].mean()*100:.1f}%")

# 轮动强度解读
if rotation_df['pre_to_during'].mean() < 0.3:
    print("  → 会前到会中板块轮动明显（重叠度<30%）")
else:
    print("  → 会前到会中板块持续性较强")

if rotation_df['during_to_post'].mean() < 0.3:
    print("  → 会中到会后板块轮动明显（重叠度<30%）")
else:
    print("  → 会中到会后板块持续性较强")


# 分析4: 各期间领涨板块特征
print("\n\n【4. 各期间领涨板块特征】")
print("-"*80)

for period in PERIODS:
    print(f"\n{period} - 最常领涨的板块:")
    
    # 统计各年份该期间的领涨板块
    sector_counts = defaultdict(int)
    for year in years:
        top_sectors = get_top_sectors_by_year(df, year, period, 3)
        for s in top_sectors:
            sector_counts[s] += 1
    
    # 排序
    sorted_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)
    for sector, count in sorted_sectors[:5]:
        print(f"  {sector}: {count}次 ({count/len(years)*100:.0f}%)")


# 分析5: 板块轮动与收益关系
print("\n\n【5. 板块轮动与收益关系】")
print("-"*80)

# 分析轮动强度与收益的关系
rotation_returns = []
for year in years:
    # 获取该年各期间收益
    pre_df = df[(df['year'] == year) & (df['period'] == '两会前5日')]
    during_df = df[(df['year'] == year) & (df['period'] == '两会期间')]
    post7_df = df[(df['year'] == year) & (df['period'] == '两会后7日')]
    
    if not pre_df.empty and not during_df.empty and not post7_df.empty:
        pre_return = pre_df['avg_return'].mean()
        during_return = during_df['avg_return'].mean()
        post7_return = post7_df['avg_return'].mean()
        
        # 计算轮动强度
        pre_sectors = get_top_sectors_by_year(df, year, '两会前5日', 5)
        during_sectors = get_top_sectors_by_year(df, year, '两会期间', 5)
        post7_sectors = get_top_sectors_by_year(df, year, '两会后7日', 5)
        
        pre_to_during = len(set(pre_sectors) & set(during_sectors)) / 5 if pre_sectors and during_sectors else 0
        during_to_post = len(set(during_sectors) & set(post7_sectors)) / 5 if during_sectors and post7_sectors else 0
        
        rotation_returns.append({
            'year': year,
            'pre_return': pre_return,
            'during_return': during_return,
            'post7_return': post7_return,
            'pre_to_during': pre_to_during,
            'during_to_post': during_to_post,
        })

rotation_returns_df = pd.DataFrame(rotation_returns)

# 计算相关性
if len(rotation_returns_df) > 3:
    corr1 = rotation_returns_df['pre_to_during'].corr(rotation_returns_df['during_return'])
    corr2 = rotation_returns_df['during_to_post'].corr(rotation_returns_df['post7_return'])
    
    print(f"\n轮动强度与收益相关性:")
    print(f"  会前→会中轮动强度 vs 会中收益: {corr1:.3f}")
    print(f"  会中→会后轮动强度 vs 会后收益: {corr2:.3f}")
    
    if abs(corr1) > 0.3:
        print(f"  → {'负相关' if corr1 < 0 else '正相关'}: 轮动{'越强' if corr1 < 0 else '越弱'}，会中收益{'越高' if corr1 < 0 else '越低'}")
    if abs(corr2) > 0.3:
        print(f"  → {'负相关' if corr2 < 0 else '正相关'}: 轮动{'越强' if corr2 < 0 else '越弱'}，会后收益{'越高' if corr2 < 0 else '越低'}")


# 分析6: 会前预期 vs 会后兑现
print("\n\n【6. 会前预期 vs 会后兑现分析】")
print("-"*80)

# 找出会前强势但会后弱势的板块（预期落空）
# 和会前弱势但会后强势的板块（政策超预期）

expectation_analysis = []
for year in years:
    # 获取会前和会后强势板块
    pre_top = set(get_top_sectors_by_year(df, year, '两会前5日', 5))
    post7_top = set(get_top_sectors_by_year(df, year, '两会后7日', 5))
    post15_top = set(get_top_sectors_by_year(df, year, '两会后15日', 5))
    
    # 会前强势且会后强势的板块（预期兑现）
    fulfilled = pre_top & post7_top
    
    # 会前强势但会后弱势的板块（预期落空）
    disappointed = pre_top - post7_top
    
    # 会前弱势但会后强势的板块（政策超预期）
    surprised = post7_top - pre_top
    
    expectation_analysis.append({
        'year': year,
        'fulfilled': fulfilled,
        'disappointed': disappointed,
        'surprised': surprised,
        'fulfilled_count': len(fulfilled),
        'disappointed_count': len(disappointed),
        'surprised_count': len(surprised),
    })

expectation_df = pd.DataFrame(expectation_analysis)

print(f"\n平均预期兑现情况:")
print(f"  预期兑现（会前强势→会后强势）: {expectation_df['fulfilled_count'].mean():.1f}个板块/年")
print(f"  预期落空（会前强势→会后弱势）: {expectation_df['disappointed_count'].mean():.1f}个板块/年")
print(f"  政策超预期（会前弱势→会后强势）: {expectation_df['surprised_count'].mean():.1f}个板块/年")

print(f"\n预期兑现率: {expectation_df['fulfilled_count'].mean() / 5 * 100:.1f}%")

# 分析哪些板块最容易预期兑现
print("\n\n最容易预期兑现的板块（会前强势且会后强势）:")
fulfilled_sectors = defaultdict(int)
for item in expectation_analysis:
    for sector in item['fulfilled']:
        fulfilled_sectors[sector] += 1

for sector, count in sorted(fulfilled_sectors.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {sector}: {count}次")


# 分析7: 板块轮动策略建议
print("\n\n【7. 板块轮动策略建议】")
print("-"*80)

print("\n基于分析结果，建议策略:")
print("\n1. 会前布局（预期阶段）:")
pre_stable_sectors = []
for sector in df['industry'].unique():
    win_rate, avg_return = calculate_sector_stability(df, sector, '两会前5日')
    if win_rate and win_rate >= 0.6 and avg_return > 0:
        pre_stable_sectors.append((sector, win_rate, avg_return))

pre_stable_sectors.sort(key=lambda x: x[2], reverse=True)
print("   稳定上涨板块（胜率≥60%）:")
for sector, win_rate, avg_return in pre_stable_sectors[:3]:
    print(f"     - {sector}: 胜率{win_rate*100:.0f}%, 平均收益{avg_return:+.2f}%")

print("\n2. 会中防守（轮动阶段）:")
during_stable_sectors = []
for sector in df['industry'].unique():
    win_rate, avg_return = calculate_sector_stability(df, sector, '两会期间')
    if win_rate and win_rate >= 0.5 and avg_return > 0:
        during_stable_sectors.append((sector, win_rate, avg_return))

during_stable_sectors.sort(key=lambda x: x[2], reverse=True)
print("   会中抗跌板块:")
for sector, win_rate, avg_return in during_stable_sectors[:3]:
    print(f"     - {sector}: 胜率{win_rate*100:.0f}%, 平均收益{avg_return:+.2f}%")

print("\n3. 会后追击（兑现阶段）:")
post_stable_sectors = []
for sector in df['industry'].unique():
    win_rate, avg_return = calculate_sector_stability(df, sector, '两会后7日')
    if win_rate and win_rate >= 0.6 and avg_return > 1.0:  # 要求平均收益>1%
        post_stable_sectors.append((sector, win_rate, avg_return))

post_stable_sectors.sort(key=lambda x: x[2], reverse=True)
print("   会后高弹性板块（胜率≥60%, 收益>1%）:")
for sector, win_rate, avg_return in post_stable_sectors[:5]:
    print(f"     - {sector}: 胜率{win_rate*100:.0f}%, 平均收益{avg_return:+.2f}%")


# 导出结果
output_data = []
for period in PERIODS:
    sector_counts = defaultdict(int)
    for year in years:
        top_sectors = get_top_sectors_by_year(df, year, period, 5)
        for s in top_sectors:
            sector_counts[s] += 1
    
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        win_rate, avg_return = calculate_sector_stability(df, sector, period)
        output_data.append({
            '期间': period,
            '板块': sector,
            '领涨次数': count,
            '胜率': f"{win_rate*100:.0f}%" if win_rate else 'N/A',
            '平均收益': f"{avg_return:+.2f}%" if avg_return else 'N/A'
        })

output_df = pd.DataFrame(output_data)
output_path = Path(__file__).parent / "lianghui_sector_rotation.csv"
output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n\n结果已保存: {output_path}")


print("\n\n" + "="*80)
print("【最终结论】")
print("="*80)

conclusion = f"""
1. 板块轮动强度:
   - 会前→会中重叠度: {rotation_df['pre_to_during'].mean()*100:.1f}%（{'轮动明显' if rotation_df['pre_to_during'].mean() < 0.3 else '持续性较强'}）
   - 会中→会后重叠度: {rotation_df['during_to_post'].mean()*100:.1f}%（{'轮动明显' if rotation_df['during_to_post'].mean() < 0.3 else '持续性较强'}）

2. 预期兑现情况:
   - 预期兑现率: {expectation_df['fulfilled_count'].mean() / 5 * 100:.1f}%
   - 平均每年{expectation_df['disappointed_count'].mean():.1f}个板块预期落空
   - 平均每年{expectation_df['surprised_count'].mean():.1f}个板块政策超预期

3. 板块轮动规律:
   {'✓' if rotation_df['pre_to_during'].mean() < 0.3 else '✗'} 会前预期资金确实会轮动
   {'✓' if rotation_df['during_to_post'].mean() < 0.3 else '✗'} 会中到会后板块继续轮动
   → 说明市场预期在不断调整，政策兑现过程存在轮动

4. 策略建议:
   - 会前: 布局稳定上涨板块（如{pre_stable_sectors[0][0] if pre_stable_sectors else 'N/A'}）
   - 会中: 防守为主，关注抗跌板块
   - 会后: 追击高弹性板块（如{post_stable_sectors[0][0] if post_stable_sectors else 'N/A'}）
   - 不要死守会前持仓，需要根据政策动向调整
"""

print(conclusion)
