"""
两会期间股票表现分析脚本 (优化版)
====================================

分析两会前5个交易日、两会期间、两会后3天/7天/15天的涨跌幅和波动情况

优化策略:
- 按需加载数据，只加载分析所需时间范围
- 使用向量化计算替代循环
- 批量处理所有股票

数据来源: ArcticDB (stock_daily库)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_svc.unified_data_manager import UnifiedDataManager
from data_svc.unified_data_query import get_stock_basic


@dataclass
class LiangHuiPeriod:
    """两会时间段定义"""
    year: int
    start_date: str  # 两会开始日期
    end_date: str    # 两会结束日期


@dataclass
class PeriodStats:
    """时间段统计结果"""
    period_name: str
    start_date: str
    end_date: str
    trading_days: int
    
    # 涨跌幅统计
    avg_return: float      # 平均涨跌幅 (%)
    max_return: float      # 最大涨跌幅 (%)
    min_return: float      # 最小涨跌幅 (%)
    median_return: float   # 中位数涨跌幅 (%)
    positive_ratio: float  # 上涨比例 (%)
    
    # 波动统计
    avg_volatility: float  # 平均波动率 (%)
    max_volatility: float  # 最大波动率 (%)
    
    # 成交量统计
    avg_volume_ratio: float  # 平均成交量比率 (相对20日均量)


# 两会时间表 (2015-2025年)
LIANGHUI_SCHEDULE = [
    LiangHuiPeriod(2025, "2025-03-04", "2025-03-11"),
    LiangHuiPeriod(2024, "2024-03-04", "2024-03-11"),
    LiangHuiPeriod(2023, "2023-03-04", "2023-03-13"),
    LiangHuiPeriod(2022, "2022-03-04", "2022-03-11"),
    LiangHuiPeriod(2021, "2021-03-04", "2021-03-11"),
    LiangHuiPeriod(2020, "2020-05-21", "2020-05-28"),
    LiangHuiPeriod(2019, "2019-03-03", "2019-03-15"),
    LiangHuiPeriod(2018, "2018-03-03", "2018-03-20"),
    LiangHuiPeriod(2017, "2017-03-03", "2017-03-15"),
    LiangHuiPeriod(2016, "2016-03-03", "2016-03-16"),
    LiangHuiPeriod(2015, "2015-03-03", "2015-03-15"),
]


class LiangHuiAnalyzer:
    """两会期间股票表现分析器 (优化版)"""
    
    def __init__(self):
        self.data_manager = UnifiedDataManager()
        self.stock_basic = get_stock_basic()
        self._cached_data = {}  # 缓存已加载的数据
        
    def _get_date_range(self, periods: List[LiangHuiPeriod]) -> Tuple[str, str]:
        """计算所有分析所需的日期范围"""
        all_dates = []
        for period in periods:
            # 每个时间段需要前后扩展30天来获取交易日
            start = pd.to_datetime(period.start_date) - timedelta(days=45)
            end = pd.to_datetime(period.end_date) + timedelta(days=45)
            all_dates.extend([start, end])
        
        min_date = min(all_dates)
        max_date = max(all_dates)
        return min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d")
    
    def load_data_for_periods(self, periods: List[LiangHuiPeriod]) -> pd.DataFrame:
        """加载指定时间段所需的所有数据"""
        start_date, end_date = self._get_date_range(periods)
        
        logger.info(f"加载数据范围: {start_date} 至 {end_date}")
        
        try:
            df = self.data_manager.read(
                library='stock_daily',
                start_date=start_date,
                end_date=end_date,
                use_cache=False
            )
            
            if df.is_empty():
                logger.error("无法加载数据，返回空DataFrame")
                return pd.DataFrame()
            
            # 转换为pandas
            pdf = df.to_pandas()
            
            # 确保日期列存在且格式正确
            pdf['date'] = pd.to_datetime(pdf['trade_date'])
            
            # 按股票和日期排序
            pdf = pdf.sort_values(['stock_code', 'date'])
            
            logger.info(f"数据加载完成: {len(pdf)} 行, {pdf['stock_code'].nunique()} 只股票")
            return pdf
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_trading_days(self, df: pd.DataFrame, start_date: str, end_date: str) -> List[str]:
        """从数据中获取指定日期范围内的交易日"""
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
        trading_days = df[mask]['date'].dt.strftime('%Y-%m-%d').unique().tolist()
        
        return sorted(trading_days)
    
    def get_previous_trading_days(self, df: pd.DataFrame, date: str, n: int) -> List[str]:
        """获取指定日期前N个交易日"""
        target_date = pd.to_datetime(date)
        all_days = sorted(df['date'].unique())
        prev_days = [d for d in all_days if d < target_date]
        return [pd.to_datetime(d).strftime('%Y-%m-%d') for d in prev_days[-n:]]
    
    def get_next_trading_days(self, df: pd.DataFrame, date: str, n: int) -> List[str]:
        """获取指定日期后N个交易日"""
        target_date = pd.to_datetime(date)
        all_days = sorted(df['date'].unique())
        next_days = [d for d in all_days if d > target_date]
        return [pd.to_datetime(d).strftime('%Y-%m-%d') for d in next_days[:n]]
    
    def analyze_all_stocks_vectorized(self, df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """
        向量化计算所有股票在指定时间段的收益率和波动率
        
        Returns:
            DataFrame with columns: stock_code, return_pct, volatility, volume_ratio
        """
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # 筛选时间范围内的数据
        mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
        period_df = df[mask].copy()
        
        if period_df.empty:
            return pd.DataFrame()
        
        # 获取每只股票的第一条和最后一条数据
        first_prices = period_df.groupby('stock_code')['close'].first().rename('start_price')
        last_prices = period_df.groupby('stock_code')['close'].last().rename('end_price')
        
        # 计算收益率
        returns = ((last_prices - first_prices) / first_prices * 100).rename('return_pct')
        
        # 计算波动率 (日收益率标准差)
        period_df['daily_return'] = period_df.groupby('stock_code')['close'].pct_change() * 100
        volatilities = period_df.groupby('stock_code')['daily_return'].std().rename('volatility')
        
        # 计算平均成交量
        avg_volumes = period_df.groupby('stock_code')['volume'].mean().rename('avg_volume')
        
        # 计算交易天数
        trading_days = period_df.groupby('stock_code').size().rename('trading_days')
        
        # 合并结果
        results = pd.concat([returns, volatilities, avg_volumes, trading_days], axis=1)
        results = results.reset_index()
        
        return results
    
    def calculate_volume_ratio(self, df: pd.DataFrame, stock_codes: List[str], 
                               start_date: str, end_date: str) -> Dict[str, float]:
        """计算成交量比率 (相对于前20个交易日)"""
        # 获取前20个交易日
        prev_days = self.get_previous_trading_days(df, start_date, 20)
        if not prev_days:
            return {code: 100.0 for code in stock_codes}
        
        prev_start = pd.to_datetime(prev_days[0])
        prev_end = pd.to_datetime(prev_days[-1])
        
        # 筛选基准期数据
        baseline_mask = (df['date'] >= prev_start) & (df['date'] <= prev_end)
        baseline_df = df[baseline_mask]
        
        # 计算基准期平均成交量
        baseline_volumes = baseline_df.groupby('stock_code')['volume'].mean()
        
        return baseline_volumes.to_dict()
    
    def analyze_period(self, df: pd.DataFrame, period_name: str, 
                       start_date: str, end_date: str) -> Optional[PeriodStats]:
        """分析指定时间段的市场表现 (向量化版本)"""
        
        # 向量化计算所有股票的收益率和波动率
        results_df = self.analyze_all_stocks_vectorized(df, start_date, end_date)
        
        if results_df.empty:
            return None
        
        # 计算成交量比率
        baseline_volumes = self.calculate_volume_ratio(df, results_df['stock_code'].tolist(), 
                                                       start_date, end_date)
        
        # 合并成交量比率
        results_df['baseline_volume'] = results_df['stock_code'].map(baseline_volumes)
        results_df['volume_ratio'] = results_df.apply(
            lambda x: (x['avg_volume'] / x['baseline_volume'] * 100) if x['baseline_volume'] > 0 else 100,
            axis=1
        )
        
        # 过滤掉NaN值
        results_df = results_df.dropna(subset=['return_pct'])
        
        if results_df.empty:
            return None
        
        returns = results_df['return_pct'].tolist()
        volatilities = results_df['volatility'].fillna(0).tolist()
        volume_ratios = results_df['volume_ratio'].tolist()
        trading_days_list = results_df['trading_days'].tolist()
        
        positive_count = sum(1 for r in returns if r > 0)
        
        return PeriodStats(
            period_name=period_name,
            start_date=start_date,
            end_date=end_date,
            trading_days=int(np.mean(trading_days_list)),
            avg_return=np.mean(returns),
            max_return=max(returns),
            min_return=min(returns),
            median_return=np.median(returns),
            positive_ratio=positive_count / len(returns) * 100,
            avg_volatility=np.mean(volatilities),
            max_volatility=max(volatilities),
            avg_volume_ratio=np.mean(volume_ratios)
        )
    
    def analyze_year(self, df: pd.DataFrame, period: LiangHuiPeriod) -> Dict[str, PeriodStats]:
        """分析某一年的两会期间表现"""
        
        logger.info(f"分析 {period.year} 年两会期间表现...")
        
        results = {}
        
        # 1. 两会前5个交易日
        pre_days = self.get_previous_trading_days(df, period.start_date, 5)
        if pre_days:
            stats = self.analyze_period(df, f"{period.year}年两会前5日", 
                                       pre_days[0], pre_days[-1])
            if stats:
                results['pre_5d'] = stats
        
        # 2. 两会期间
        stats = self.analyze_period(df, f"{period.year}年两会期间",
                                   period.start_date, period.end_date)
        if stats:
            results['during'] = stats
        
        # 3. 两会后3个交易日
        post_3d_days = self.get_next_trading_days(df, period.end_date, 3)
        if post_3d_days:
            stats = self.analyze_period(df, f"{period.year}年两会后3日",
                                       post_3d_days[0], post_3d_days[-1])
            if stats:
                results['post_3d'] = stats
        
        # 4. 两会后7个交易日
        post_7d_days = self.get_next_trading_days(df, period.end_date, 7)
        if post_7d_days:
            stats = self.analyze_period(df, f"{period.year}年两会后7日",
                                       post_7d_days[0], post_7d_days[-1])
            if stats:
                results['post_7d'] = stats
        
        # 5. 两会后15个交易日
        post_15d_days = self.get_next_trading_days(df, period.end_date, 15)
        if post_15d_days:
            stats = self.analyze_period(df, f"{period.year}年两会后15日",
                                       post_15d_days[0], post_15d_days[-1])
            if stats:
                results['post_15d'] = stats
        
        return results
    
    def _is_index(self, symbol: str) -> bool:
        """判断是否为指数"""
        if symbol.isdigit():
            if symbol.startswith('000') or symbol.startswith('399') or symbol.startswith('899'):
                return True
        return False
    
    def run_analysis(self, years: List[int] = None) -> Dict[int, Dict[str, PeriodStats]]:
        """
        运行两会期间表现分析
        
        Args:
            years: 要分析的年份列表，None表示分析所有年份
        """
        # 筛选年份
        periods_to_analyze = LIANGHUI_SCHEDULE
        if years:
            periods_to_analyze = [p for p in LIANGHUI_SCHEDULE if p.year in years]
        
        # 一次性加载所有需要的数据
        df = self.load_data_for_periods(periods_to_analyze)
        
        if df.empty:
            logger.error("数据加载失败，无法进行分析")
            return {}
        
        # 过滤掉指数
        df = df[~df['stock_code'].apply(self._is_index)]
        logger.info(f"过滤指数后剩余股票: {df['stock_code'].nunique()} 只")
        
        all_results = {}
        for period in periods_to_analyze:
            year_results = self.analyze_year(df, period)
            if year_results:
                all_results[period.year] = year_results
        
        return all_results
    
    def print_summary(self, results: Dict[int, Dict[str, PeriodStats]]):
        """打印分析结果摘要"""
        
        print("\n" + "="*100)
        print("两会期间股票表现分析报告")
        print("="*100)
        
        # 按时间段汇总
        periods = ['pre_5d', 'during', 'post_3d', 'post_7d', 'post_15d']
        period_names = {
            'pre_5d': '两会前5日',
            'during': '两会期间',
            'post_3d': '两会后3日',
            'post_7d': '两会后7日',
            'post_15d': '两会后15日'
        }
        
        for period_key in periods:
            print(f"\n【{period_names[period_key]}】")
            print("-" * 100)
            
            # 收集所有年份的数据
            all_returns = []
            all_volatilities = []
            all_positive_ratios = []
            
            for year, year_results in sorted(results.items()):
                if period_key in year_results:
                    stats = year_results[period_key]
                    all_returns.append(stats.avg_return)
                    all_volatilities.append(stats.avg_volatility)
                    all_positive_ratios.append(stats.positive_ratio)
                    
                    print(f"  {year}年: 平均收益={stats.avg_return:+.2f}%, "
                          f"中位数={stats.median_return:+.2f}%, "
                          f"上涨比例={stats.positive_ratio:.1f}%, "
                          f"波动率={stats.avg_volatility:.2f}%")
            
            if all_returns:
                print("-" * 100)
                print(f"  历年平均: 平均收益={np.mean(all_returns):+.2f}%, "
                      f"波动率={np.mean(all_volatilities):.2f}%, "
                      f"上涨比例={np.mean(all_positive_ratios):.1f}%")
                print(f"  收益范围: {min(all_returns):+.2f}% ~ {max(all_returns):+.2f}%")
        
        print("\n" + "="*100)


def main():
    """主函数"""
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    analyzer = LiangHuiAnalyzer()
    
    # 分析所有年份
    results = analyzer.run_analysis(years=None)
    
    # 打印结果
    analyzer.print_summary(results)
    
    # 保存详细结果到CSV
    save_detailed_results(results)


def save_detailed_results(results: Dict[int, Dict[str, PeriodStats]]):
    """保存详细结果到CSV文件"""
    
    rows = []
    for year, year_results in sorted(results.items()):
        for period_key, stats in year_results.items():
            rows.append({
                '年份': year,
                '时间段': stats.period_name,
                '开始日期': stats.start_date,
                '结束日期': stats.end_date,
                '交易日数': stats.trading_days,
                '平均收益率(%)': round(stats.avg_return, 2),
                '中位数收益率(%)': round(stats.median_return, 2),
                '最大收益率(%)': round(stats.max_return, 2),
                '最小收益率(%)': round(stats.min_return, 2),
                '上涨比例(%)': round(stats.positive_ratio, 2),
                '平均波动率(%)': round(stats.avg_volatility, 2),
                '最大波动率(%)': round(stats.max_volatility, 2),
                '成交量比率(%)': round(stats.avg_volume_ratio, 2),
            })
    
    df = pd.DataFrame(rows)
    output_path = Path(__file__).parent / "lianghui_analysis_results.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n详细结果已保存到: {output_path}")
    
    # 同时打印表格
    print("\n详细数据表格:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
