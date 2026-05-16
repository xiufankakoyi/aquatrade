"""
两会期间行业板块收益分析
========================

基于个股行业分类，分析各行业在两会期间的表现
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.unified_data_manager import get_unified_manager
from data_svc.unified_data_query import get_stock_basic


@dataclass
class LianghuiPeriod:
    """两会期间定义"""
    year: int
    name: str
    start_date: str
    end_date: str


# 两会期间定义 (2015-2025)
LIANGHUI_PERIODS = [
    LianghuiPeriod(2025, "两会前5日", "2025-02-25", "2025-03-03"),
    LianghuiPeriod(2025, "两会期间", "2025-03-04", "2025-03-11"),
    LianghuiPeriod(2025, "两会后3日", "2025-03-12", "2025-03-14"),
    LianghuiPeriod(2025, "两会后7日", "2025-03-12", "2025-03-20"),
    LianghuiPeriod(2025, "两会后15日", "2025-03-12", "2025-04-01"),
    
    LianghuiPeriod(2024, "两会前5日", "2024-02-26", "2024-03-01"),
    LianghuiPeriod(2024, "两会期间", "2024-03-04", "2024-03-11"),
    LianghuiPeriod(2024, "两会后3日", "2024-03-12", "2024-03-14"),
    LianghuiPeriod(2024, "两会后7日", "2024-03-12", "2024-03-20"),
    LianghuiPeriod(2024, "两会后15日", "2024-03-12", "2024-04-01"),
    
    LianghuiPeriod(2023, "两会前5日", "2023-02-27", "2023-03-03"),
    LianghuiPeriod(2023, "两会期间", "2023-03-04", "2023-03-13"),
    LianghuiPeriod(2023, "两会后3日", "2023-03-14", "2023-03-16"),
    LianghuiPeriod(2023, "两会后7日", "2023-03-14", "2023-03-22"),
    LianghuiPeriod(2023, "两会后15日", "2023-03-14", "2023-04-03"),
    
    LianghuiPeriod(2022, "两会前5日", "2022-02-25", "2022-03-03"),
    LianghuiPeriod(2022, "两会期间", "2022-03-04", "2022-03-11"),
    LianghuiPeriod(2022, "两会后3日", "2022-03-14", "2022-03-16"),
    LianghuiPeriod(2022, "两会后7日", "2022-03-14", "2022-03-22"),
    LianghuiPeriod(2022, "两会后15日", "2022-03-14", "2022-04-01"),
    
    LianghuiPeriod(2021, "两会前5日", "2021-02-25", "2021-03-03"),
    LianghuiPeriod(2021, "两会期间", "2021-03-04", "2021-03-11"),
    LianghuiPeriod(2021, "两会后3日", "2021-03-12", "2021-03-16"),
    LianghuiPeriod(2021, "两会后7日", "2021-03-12", "2021-03-22"),
    LianghuiPeriod(2021, "两会后15日", "2021-03-12", "2021-04-01"),
    
    LianghuiPeriod(2020, "两会前5日", "2020-05-14", "2020-05-20"),
    LianghuiPeriod(2020, "两会期间", "2020-05-21", "2020-05-28"),
    LianghuiPeriod(2020, "两会后3日", "2020-05-29", "2020-06-02"),
    LianghuiPeriod(2020, "两会后7日", "2020-05-29", "2020-06-08"),
    LianghuiPeriod(2020, "两会后15日", "2020-05-29", "2020-06-18"),
    
    LianghuiPeriod(2019, "两会前5日", "2019-02-25", "2019-03-01"),
    LianghuiPeriod(2019, "两会期间", "2019-03-03", "2019-03-15"),
    LianghuiPeriod(2019, "两会后3日", "2019-03-18", "2019-03-20"),
    LianghuiPeriod(2019, "两会后7日", "2019-03-18", "2019-03-26"),
    LianghuiPeriod(2019, "两会后15日", "2019-03-18", "2019-04-08"),
    
    LianghuiPeriod(2018, "两会前5日", "2018-02-26", "2018-03-02"),
    LianghuiPeriod(2018, "两会期间", "2018-03-03", "2018-03-20"),
    LianghuiPeriod(2018, "两会后3日", "2018-03-21", "2018-03-23"),
    LianghuiPeriod(2018, "两会后7日", "2018-03-21", "2018-03-29"),
    LianghuiPeriod(2018, "两会后15日", "2018-03-21", "2018-04-12"),
    
    LianghuiPeriod(2017, "两会前5日", "2017-02-24", "2017-03-02"),
    LianghuiPeriod(2017, "两会期间", "2017-03-03", "2017-03-15"),
    LianghuiPeriod(2017, "两会后3日", "2017-03-16", "2017-03-20"),
    LianghuiPeriod(2017, "两会后7日", "2017-03-16", "2017-03-24"),
    LianghuiPeriod(2017, "两会后15日", "2017-03-16", "2017-04-07"),
    
    LianghuiPeriod(2016, "两会前5日", "2016-02-25", "2016-03-02"),
    LianghuiPeriod(2016, "两会期间", "2016-03-03", "2016-03-16"),
    LianghuiPeriod(2016, "两会后3日", "2016-03-17", "2016-03-21"),
    LianghuiPeriod(2016, "两会后7日", "2016-03-17", "2016-03-25"),
    LianghuiPeriod(2016, "两会后15日", "2016-03-17", "2016-04-07"),
    
    LianghuiPeriod(2015, "两会前5日", "2015-02-17", "2015-03-02"),
    LianghuiPeriod(2015, "两会期间", "2015-03-03", "2015-03-15"),
    LianghuiPeriod(2015, "两会后3日", "2015-03-16", "2015-03-18"),
    LianghuiPeriod(2015, "两会后7日", "2015-03-16", "2015-03-24"),
    LianghuiPeriod(2015, "两会后15日", "2015-03-16", "2015-04-03"),
]


class IndustryLianghuiAnalyzer:
    """两会期间行业分析器"""
    
    def __init__(self):
        self.manager = get_unified_manager()
        self.stock_basic = get_stock_basic()
        self._load_stock_industry_map()
        
    def _load_stock_industry_map(self):
        """加载股票行业映射"""
        if self.stock_basic is not None and not self.stock_basic.empty:
            # 创建股票代码到行业的映射
            self.stock_industry_map = dict(zip(
                self.stock_basic['code'].astype(str),
                self.stock_basic['industry']
            ))
            print(f"加载了 {len(self.stock_industry_map)} 只股票的行业信息")
        else:
            self.stock_industry_map = {}
            print("警告: 无法加载股票行业信息")
    
    def get_stock_industry(self, stock_code: str) -> str:
        """获取股票所属行业"""
        # 提取纯数字代码
        code = str(stock_code).split('.')[0]
        return self.stock_industry_map.get(code, "未知")
    
    def analyze_industry_performance(self, period: LianghuiPeriod) -> pd.DataFrame:
        """分析指定期间各行业表现"""
        print(f"\n分析 {period.year} 年 {period.name} ({period.start_date} 至 {period.end_date})")
        
        # 加载数据
        df = self.manager.read('stock_daily', 
                              start_date=period.start_date, 
                              end_date=period.end_date)
        
        if df.is_empty():
            print(f"  无数据")
            return pd.DataFrame()
        
        df = df.to_pandas()
        
        # 确定股票代码列名
        code_col = 'stock_code' if 'stock_code' in df.columns else 'symbol'
        if code_col not in df.columns:
            print(f"  错误: 找不到股票代码列")
            return pd.DataFrame()
        
        # 添加行业信息
        df['industry'] = df[code_col].apply(self.get_stock_industry)
        
        # 过滤掉指数和未知行业
        df = df[~df['industry'].isin(['未知', ''])]
        
        if df.empty:
            print(f"  无有效股票数据")
            return pd.DataFrame()
        
        # 计算每只股票在期间内的收益率
        df['date'] = pd.to_datetime(df['trade_date'])
        
        # 按股票分组计算收益
        stock_returns = []
        for stock_code, group in df.groupby(code_col):
            group = group.sort_values('date')
            if len(group) >= 2:
                start_price = group.iloc[0]['close']
                end_price = group.iloc[-1]['close']
                return_pct = (end_price - start_price) / start_price * 100
                industry = group.iloc[0]['industry']
                stock_returns.append({
                    'stock_code': stock_code,
                    'industry': industry,
                    'return_pct': return_pct,
                    'start_price': start_price,
                    'end_price': end_price,
                    'trading_days': len(group)
                })
        
        if not stock_returns:
            return pd.DataFrame()
        
        stock_df = pd.DataFrame(stock_returns)
        
        # 按行业统计
        industry_stats = []
        for industry, group in stock_df.groupby('industry'):
            if len(group) >= 3:  # 至少3只股票才统计
                industry_stats.append({
                    'year': period.year,
                    'period': period.name,
                    'industry': industry,
                    'stock_count': len(group),
                    'avg_return': group['return_pct'].mean(),
                    'median_return': group['return_pct'].median(),
                    'max_return': group['return_pct'].max(),
                    'min_return': group['return_pct'].min(),
                    'positive_ratio': (group['return_pct'] > 0).mean() * 100,
                    'std_return': group['return_pct'].std(),
                })
        
        result_df = pd.DataFrame(industry_stats)
        print(f"  统计了 {len(result_df)} 个行业")
        return result_df
    
    def run_full_analysis(self) -> pd.DataFrame:
        """运行完整分析"""
        print("="*80)
        print("两会期间行业板块收益分析")
        print("="*80)
        
        all_results = []
        for period in LIANGHUI_PERIODS:
            result = self.analyze_industry_performance(period)
            if not result.empty:
                all_results.append(result)
        
        if not all_results:
            print("\n无分析结果")
            return pd.DataFrame()
        
        combined = pd.concat(all_results, ignore_index=True)
        
        # 保存详细结果
        output_path = Path(__file__).parent / "lianghui_industry_detail.csv"
        combined.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n详细结果已保存: {output_path}")
        
        return combined
    
    def generate_summary(self, df: pd.DataFrame):
        """生成汇总统计"""
        if df.empty:
            return
        
        print("\n\n" + "="*80)
        print("行业表现汇总")
        print("="*80)
        
        # 1. 各行业在两会期间的平均表现
        print("\n【1. 各行业在两会期间的平均表现】")
        print("-"*80)
        
        period_names = ['两会前5日', '两会期间', '两会后3日', '两会后7日', '两会后15日']
        
        for period_name in period_names:
            period_df = df[df['period'] == period_name]
            if period_df.empty:
                continue
            
            print(f"\n{period_name}:")
            avg_by_industry = period_df.groupby('industry')['avg_return'].mean().sort_values(ascending=False)
            print(f"  表现最好的5个行业:")
            for i, (industry, avg_ret) in enumerate(avg_by_industry.head(5).items(), 1):
                print(f"    {i}. {industry}: {avg_ret:+.2f}%")
            
            print(f"  表现最差的5个行业:")
            for i, (industry, avg_ret) in enumerate(avg_by_industry.tail(5).items(), 1):
                print(f"    {i}. {industry}: {avg_ret:+.2f}%")
        
        # 2. 历年两会期间表现最稳定的行业
        print("\n\n【2. 两会期间表现最稳定的行业(胜率>60%且平均收益>0)】")
        print("-"*80)
        
        during_df = df[df['period'] == '两会期间']
        if not during_df.empty:
            industry_stats = []
            for industry, group in during_df.groupby('industry'):
                if len(group) >= 5:  # 至少5年数据
                    avg_return = group['avg_return'].mean()
                    avg_positive_ratio = group['positive_ratio'].mean()
                    if avg_positive_ratio > 60 and avg_return > 0:
                        industry_stats.append({
                            'industry': industry,
                            'avg_return': avg_return,
                            'avg_positive_ratio': avg_positive_ratio,
                            'years': len(group)
                        })
            
            if industry_stats:
                stable_df = pd.DataFrame(industry_stats).sort_values('avg_return', ascending=False)
                for _, row in stable_df.head(10).iterrows():
                    print(f"  {row['industry']}: 平均收益{row['avg_return']:+.2f}%, 平均胜率{row['avg_positive_ratio']:.1f}% ({row['years']}年)")
        
        # 3. 会后弹性最大的行业
        print("\n\n【3. 会后15日弹性最大的行业】")
        print("-"*80)
        
        post_df = df[df['period'] == '两会后15日']
        if not post_df.empty:
            elasticity_stats = []
            for industry, group in post_df.groupby('industry'):
                if len(group) >= 5:
                    avg_return = group['avg_return'].mean()
                    max_return = group['max_return'].mean()
                    elasticity_stats.append({
                        'industry': industry,
                        'avg_return': avg_return,
                        'max_return': max_return,
                        'years': len(group)
                    })
            
            if elasticity_stats:
                elastic_df = pd.DataFrame(elasticity_stats).sort_values('avg_return', ascending=False)
                print("  平均收益最高的行业:")
                for _, row in elastic_df.head(5).iterrows():
                    print(f"    {row['industry']}: {row['avg_return']:+.2f}% (最高{row['max_return']:+.2f}%, {row['years']}年)")
        
        # 4. 生成汇总CSV
        summary_data = []
        for period_name in period_names:
            period_df = df[df['period'] == period_name]
            if period_df.empty:
                continue
            
            avg_by_industry = period_df.groupby('industry')['avg_return'].mean()
            for industry, avg_ret in avg_by_industry.items():
                summary_data.append({
                    'period': period_name,
                    'industry': industry,
                    'avg_return': avg_ret,
                    'years': len(period_df[period_df['industry'] == industry])
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_path = Path(__file__).parent / "lianghui_industry_summary.csv"
            summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
            print(f"\n汇总结果已保存: {summary_path}")


if __name__ == "__main__":
    analyzer = IndustryLianghuiAnalyzer()
    results = analyzer.run_full_analysis()
    
    if not results.empty:
        analyzer.generate_summary(results)
        
        print("\n\n" + "="*80)
        print("分析完成!")
        print("="*80)
        print("""
输出文件:
1. lianghui_industry_detail.csv - 各行业每年各期间的详细表现
2. lianghui_industry_summary.csv - 各行业各期间的平均收益汇总

使用建议:
- 查看哪些行业在两会期间最抗跌
- 查看哪些行业会后弹性最大
- 结合当年政策热点选择板块
        """)
    else:
        print("\n分析失败: 未获取到有效数据")
