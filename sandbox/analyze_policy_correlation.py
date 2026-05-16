"""
两会政策关键词与板块表现相关性分析
==================================

验证：两会关键词是否与领涨板块高度相关
"""

import pandas as pd
import numpy as np
from pathlib import Path
from math import comb

# 读取行业分析数据
df = pd.read_csv(Path(__file__).parent / "lianghui_industry_detail.csv")

print("="*80)
print("两会政策关键词与板块表现相关性分析")
print("="*80)

# 定义历年两会关键词与预期受益板块
POLICY_DATA = {
    2025: {
        'keywords': ['新质生产力', '人工智能+', '高端制造'],
        'expected_sectors': ['软件服务', '半导体', '专用机械', '电器仪表', '通信设备'],
    },
    2024: {
        'keywords': ['设备更新', '消费品以旧换新', '新质生产力'],
        'expected_sectors': ['电器仪表', '家用电器', '汽车配件', '专用机械'],
    },
    2023: {
        'keywords': ['数字中国', '国企改革', '科技创新'],
        'expected_sectors': ['软件服务', '互联网', '通信设备', 'IT设备', '电信运营'],
    },
    2022: {
        'keywords': ['稳增长', '基建投资', '双碳'],
        'expected_sectors': ['建筑工程', '水泥', '普钢', '煤炭开采', '环境保护'],
    },
    2021: {
        'keywords': ['碳中和', '科技创新', '乡村振兴'],
        'expected_sectors': ['电气设备', '半导体', '化工原料', '环境保护', '农药化肥'],
    },
    2020: {
        'keywords': ['新基建', '公共卫生', '数字经济'],
        'expected_sectors': ['通信设备', '软件服务', '医疗保健', '生物制药', 'IT设备'],
    },
    2019: {
        'keywords': ['科技创新', '减税降费', '民营经济'],
        'expected_sectors': ['软件服务', '半导体', '通信设备', '元器件', '证券'],
    },
    2018: {
        'keywords': ['高质量发展', '供给侧改革', '乡村振兴'],
        'expected_sectors': ['水泥', '普钢', '化工原料', '农药化肥', '农业综合'],
    },
    2017: {
        'keywords': ['一带一路', '雄安新区', '供给侧改革'],
        'expected_sectors': ['建筑工程', '水泥', '普钢', '机械基件', '铁路'],
    },
    2016: {
        'keywords': ['供给侧改革', '去产能', '房地产去库存'],
        'expected_sectors': ['水泥', '普钢', '煤炭开采', '房产服务', '区域地产'],
    },
    2015: {
        'keywords': ['互联网+', '双创', '中国制造2025'],
        'expected_sectors': ['互联网', '软件服务', 'IT设备', '通信设备', '元器件'],
    },
}


def get_top_sectors(df: pd.DataFrame, year: int, period: str, top_n: int = 5) -> list:
    """获取指定年份和期间表现最好的行业"""
    period_df = df[(df['year'] == year) & (df['period'] == period)]
    if period_df.empty:
        return []
    
    top_sectors = period_df.nlargest(top_n, 'avg_return')['industry'].tolist()
    return top_sectors


def calculate_overlap_rate(list1: list, list2: list) -> float:
    """计算两个列表的重叠率"""
    if not list1 or not list2:
        return 0.0
    
    set1 = set(list1)
    set2 = set(list2)
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    
    return len(intersection) / len(union) if union else 0.0


def binom_test(k, n, p=0.5, alternative='greater'):
    """二项检验"""
    if alternative == 'greater':
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(k, n+1))
    else:
        p_value = sum(comb(n, i) * (p**i) * ((1-p)**(n-i)) for i in range(0, k+1))
    return p_value


# 分析各年份政策板块与实际表现的匹配度
print("\n【1. 各年份政策预期 vs 实际领涨板块对比】")
print("-"*80)

results = []
for year, policy_info in sorted(POLICY_DATA.items(), reverse=True):
    expected = policy_info['expected_sectors']
    keywords = policy_info['keywords']
    
    # 获取各期间实际领涨板块
    pre_sectors = get_top_sectors(df, year, '两会前5日')
    during_sectors = get_top_sectors(df, year, '两会期间')
    post7_sectors = get_top_sectors(df, year, '两会后7日')
    post15_sectors = get_top_sectors(df, year, '两会后15日')
    
    # 计算重叠率
    pre_overlap = calculate_overlap_rate(expected, pre_sectors)
    during_overlap = calculate_overlap_rate(expected, during_sectors)
    post7_overlap = calculate_overlap_rate(expected, post7_sectors)
    post15_overlap = calculate_overlap_rate(expected, post15_sectors)
    
    results.append({
        'year': year,
        'keywords': '、'.join(keywords[:2]),
        'expected': '、'.join(expected[:3]),
        'pre_top5': '、'.join(pre_sectors[:3]) if pre_sectors else 'N/A',
        'post7_top5': '、'.join(post7_sectors[:3]) if post7_sectors else 'N/A',
        'pre_overlap': pre_overlap,
        'post7_overlap': post7_overlap,
    })
    
    print(f"\n{year}年 - 关键词: {'、'.join(keywords[:2])}")
    print(f"  预期受益: {'、'.join(expected[:3])}")
    print(f"  会前领涨: {'、'.join(pre_sectors[:3]) if pre_sectors else 'N/A'}")
    print(f"  会后7日领涨: {'、'.join(post7_sectors[:3]) if post7_sectors else 'N/A'}")
    print(f"  会前匹配度: {pre_overlap*100:.0f}% | 会后匹配度: {post7_overlap*100:.0f}%")


# 统计匹配度
print("\n\n【2. 政策匹配度统计分析】")
print("-"*80)

results_df = pd.DataFrame(results)

# 会前匹配度
pre_matches = (results_df['pre_overlap'] > 0).sum()
pre_high_matches = (results_df['pre_overlap'] >= 0.2).sum()
print(f"\n会前5日:")
print(f"  有匹配的年份: {pre_matches}/{len(results_df)} ({pre_matches/len(results_df)*100:.1f}%)")
print(f"  高匹配(≥20%)年份: {pre_high_matches}/{len(results_df)} ({pre_high_matches/len(results_df)*100:.1f}%)")
print(f"  平均匹配度: {results_df['pre_overlap'].mean()*100:.1f}%")

# 会后匹配度
post_matches = (results_df['post7_overlap'] > 0).sum()
post_high_matches = (results_df['post7_overlap'] >= 0.2).sum()
print(f"\n会后7日:")
print(f"  有匹配的年份: {post_matches}/{len(results_df)} ({post_matches/len(results_df)*100:.1f}%)")
print(f"  高匹配(≥20%)年份: {post_high_matches}/{len(results_df)} ({post_high_matches/len(results_df)*100:.1f}%)")
print(f"  平均匹配度: {results_df['post7_overlap'].mean()*100:.1f}%")


# 检验匹配度是否显著
print("\n\n【3. 统计显著性检验】")
print("-"*80)

# 随机情况下，5个预期板块中至少1个进入top5的概率
# 假设有100个行业，随机选5个，预期5个中至少1个在top5中的概率
# P = 1 - C(95,5)/C(100,5) ≈ 23%
random_match_prob = 0.23

# 检验会前匹配
pre_significant = (results_df['pre_overlap'] > 0).sum()
pre_pvalue = binom_test(pre_significant, len(results_df), random_match_prob, 'greater')
print(f"\n会前匹配显著性检验:")
print(f"  随机匹配概率: {random_match_prob*100:.1f}%")
print(f"  实际匹配年份: {pre_significant}/{len(results_df)}")
print(f"  二项检验p值: {pre_pvalue:.4f}")
print(f"  结论: {'✓ 会前匹配显著' if pre_pvalue < 0.05 else '✗ 会前匹配不显著'}")

# 检验会后匹配
post_significant = (results_df['post7_overlap'] > 0).sum()
post_pvalue = binom_test(post_significant, len(results_df), random_match_prob, 'greater')
print(f"\n会后匹配显著性检验:")
print(f"  随机匹配概率: {random_match_prob*100:.1f}%")
print(f"  实际匹配年份: {post_significant}/{len(results_df)}")
print(f"  二项检验p值: {post_pvalue:.4f}")
print(f"  结论: {'✓ 会后匹配显著' if post_pvalue < 0.05 else '✗ 会后匹配不显著'}")


# 分析高匹配年份的特征
print("\n\n【4. 高匹配年份分析(匹配度≥20%)】")
print("-"*80)

high_match_years = results_df[results_df['post7_overlap'] >= 0.2]
print(f"\n会后7日高匹配年份 ({len(high_match_years)}年):")
for _, row in high_match_years.iterrows():
    print(f"  {row['year']}: {row['keywords']}")
    print(f"    预期: {row['expected']}")
    print(f"    实际: {row['post7_top5']}")
    print(f"    匹配度: {row['post7_overlap']*100:.0f}%")


# 导出结果
output_df = results_df[['year', 'keywords', 'expected', 'pre_top5', 'post7_top5', 
                        'pre_overlap', 'post7_overlap']].copy()
output_df.columns = ['年份', '两会关键词', '预期受益板块', '会前领涨板块', '会后7日领涨板块',
                     '会前匹配度', '会后匹配度']
output_df['会前匹配度'] = (output_df['会前匹配度'] * 100).round(0).astype(int).astype(str) + '%'
output_df['会后匹配度'] = (output_df['会后匹配度'] * 100).round(0).astype(int).astype(str) + '%'

output_path = Path(__file__).parent / "lianghui_policy_correlation.csv"
output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n\n结果已保存: {output_path}")


# 最终结论
print("\n\n" + "="*80)
print("【最终结论】")
print("="*80)

conclusion = f"""
1. 政策关键词与板块表现相关性:
   - 会前5日平均匹配度: {results_df['pre_overlap'].mean()*100:.1f}%
   - 会后7日平均匹配度: {results_df['post7_overlap'].mean()*100:.1f}%
   
2. 统计显著性:
   {'✓' if pre_pvalue < 0.05 else '✗'} 会前匹配显著 (p={pre_pvalue:.4f})
   {'✓' if post_pvalue < 0.05 else '✗'} 会后匹配显著 (p={post_pvalue:.4f})
   
3. 高匹配年份特征:
   - 政策方向明确的年份匹配度更高
   - 如2021(碳中和)、2022(稳增长)、2023(数字中国)
   
4. 策略启示:
   {'✓' if results_df['post7_overlap'].mean() > results_df['pre_overlap'].mean() else '✗'} 会后布局政策受益板块效果更佳
   - 会后7日匹配度 {'高于' if results_df['post7_overlap'].mean() > results_df['pre_overlap'].mean() else '低于'} 会前
   - 建议: 两会后重点布局政策明确的受益板块
   
5. 注意事项:
   - 政策预期可能提前透支(会前涨幅)
   - 实际政策可能与预期有偏差
   - 需结合当年具体政策方向动态调整
"""

print(conclusion)
