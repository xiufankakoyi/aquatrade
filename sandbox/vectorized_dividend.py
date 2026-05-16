"""
向量化分红结算模块
=================
使用 Polars 向量化操作替代 Python 循环，批量处理分红和送转股。

核心优化:
1. 向量化检测除权变化 (adj_factor 变动)
2. 批量计算分红金额
3. 批量计算送转股数
4. 一次性更新持仓

使用方法:
    from sandbox.vectorized_dividend import DividendCalculator
    
    calculator = DividendCalculator()
    
    # 计算分红
    dividends = calculator.calculate_dividends(
        portfolio={'000001.SZ': 1000, '000002.SZ': 2000},
        prev_day_data=prev_df,  # 昨日数据 Polars DataFrame
        curr_day_data=curr_df   # 今日数据 Polars DataFrame
    )
    
    # 应用分红
    new_portfolio, cash_adjustment = calculator.apply_dividends(dividends)
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import time

import pandas as pd
import polars as pl
import numpy as np


@dataclass
class DividendEvent:
    """分红事件数据结构"""
    stock_code: str
    date: str
    dividend_type: str  # 'cash' | 'split' | 'none'
    dividend_per_share: float = 0.0
    total_dividend: float = 0.0
    old_shares: int = 0
    new_shares: int = 0
    factor_change: float = 0.0


class DividendCalculator:
    """
    向量化分红计算器
    
    使用 Polars 向量化操作批量处理分红事件，
    相比传统的 Python 循环，性能提升 10-100 倍。
    """
    
    # 股本变化阈值 (<5% 视为现金分红，>=5% 视为送转/拆股)
    SHARES_CHANGE_THRESHOLD = 0.05
    
    def __init__(self):
        """初始化分红计算器"""
        self._perf_stats = {
            'total_calls': 0,
            'total_duration': 0.0,
            'total_events': 0
        }
    
    def calculate_dividends(
        self,
        portfolio: Dict[str, int],
        prev_day_data: pl.DataFrame,
        curr_day_data: pl.DataFrame,
        date_str: str
    ) -> List[DividendEvent]:
        """
        【核心方法】向量化计算分红事件
        
        一次性处理所有持仓股票的分红检测和计算。
        
        Args:
            portfolio: 当前持仓 {stock_code: shares}
            prev_day_data: 昨日股票池数据 (Polars DataFrame)
            curr_day_data: 今日股票池数据 (Polars DataFrame)
            date_str: 当前日期 (YYYY-MM-DD)
        
        Returns:
            List[DividendEvent]: 分红事件列表
        """
        start_time = time.time()
        
        if not portfolio:
            return []
        
        # 1. 将持仓转换为 Polars DataFrame
        portfolio_df = pl.DataFrame([
            {'stock_code': code, 'shares': shares}
            for code, shares in portfolio.items()
        ])
        
        # 2. Join 两日数据
        comparison = self._prepare_comparison_data(
            portfolio_df, prev_day_data, curr_day_data
        )
        
        if comparison.is_empty():
            return []
        
        # 3. 向量化检测除权变化
        comparison = self._detect_factor_changes(comparison)
        
        # 4. 分类处理现金分红和送转股
        comparison = self._classify_dividend_type(comparison)
        
        # 5. 计算分红金额和送转股数
        comparison = self._calculate_dividend_amounts(comparison)
        
        # 6. 转换为事件列表
        events = self._to_dividend_events(comparison, date_str)
        
        # 更新性能统计
        duration = time.time() - start_time
        self._perf_stats['total_calls'] += 1
        self._perf_stats['total_duration'] += duration
        self._perf_stats['total_events'] += len(events)
        
        return events
    
    def _prepare_comparison_data(
        self,
        portfolio_df: pl.DataFrame,
        prev_day_data: pl.DataFrame,
        curr_day_data: pl.DataFrame
    ) -> pl.DataFrame:
        """
        准备对比数据 - Join 持仓和两日数据
        """
        # 确保有必要列
        required_cols = ['stock_code', 'adj_factor', 'close']
        
        # 处理昨日数据
        prev_cols = [c for c in required_cols if c in prev_day_data.columns]
        if not prev_cols:
            return pl.DataFrame()
        
        prev_subset = prev_day_data.select(prev_cols)
        
        # 处理今日数据
        curr_cols = [c for c in required_cols if c in curr_day_data.columns]
        if not curr_cols:
            return pl.DataFrame()
        
        curr_subset = curr_day_data.select(curr_cols)
        
        # Join 持仓和昨日数据
        with_prev = portfolio_df.join(
            prev_subset,
            left_on='stock_code',
            right_on='stock_code',
            how='inner'
        ).rename({
            'adj_factor': 'prev_factor',
            'close': 'prev_close'
        })
        
        # Join 今日数据
        comparison = with_prev.join(
            curr_subset,
            left_on='stock_code',
            right_on='stock_code',
            how='inner'
        ).rename({
            'adj_factor': 'curr_factor',
            'close': 'curr_close'
        })
        
        # 添加 total_mv 列（如果有）
        if 'total_mv' in prev_day_data.columns:
            mv_prev = prev_day_data.select(['stock_code', 'total_mv']).rename({'total_mv': 'prev_mv'})
            comparison = comparison.join(mv_prev, on='stock_code', how='left')
        else:
            comparison = comparison.with_columns(pl.lit(None).alias('prev_mv'))
        
        if 'total_mv' in curr_day_data.columns:
            mv_curr = curr_day_data.select(['stock_code', 'total_mv']).rename({'total_mv': 'curr_mv'})
            comparison = comparison.join(mv_curr, on='stock_code', how='left')
        else:
            comparison = comparison.with_columns(pl.lit(None).alias('curr_mv'))
        
        return comparison
    
    def _detect_factor_changes(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        向量化检测复权因子变化
        """
        return df.with_columns([
            # 因子变化比例
            (pl.col('curr_factor') / pl.col('prev_factor')).alias('factor_ratio'),
            # 因子变化绝对值
            (pl.col('curr_factor') - pl.col('prev_factor')).abs().alias('factor_diff'),
        ]).with_columns([
            # 是否发生除权 (因子变化 > 1e-6)
            (pl.col('factor_diff') > 1e-6).alias('has_factor_change'),
        ])
    
    def _classify_dividend_type(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        分类分红类型：现金分红 vs 送转/拆股
        
        基于总股本变化比例判断：
        - < 5%: 现金分红
        - >= 5%: 送转/拆股
        """
        # 计算总股本 (total_mv / close)
        df = df.with_columns([
            pl.when(pl.col('prev_close') > 0)
            .then(pl.col('prev_mv') / pl.col('prev_close'))
            .otherwise(None)
            .alias('prev_shares_total'),
        ]).with_columns([
            pl.when(pl.col('curr_close') > 0)
            .then(pl.col('curr_mv') / pl.col('curr_close'))
            .otherwise(None)
            .alias('curr_shares_total'),
        ])
        
        # 计算股本变化比例
        df = df.with_columns([
            pl.when(pl.col('prev_shares_total').is_not_null() & (pl.col('prev_shares_total') > 0))
            .then((pl.col('curr_shares_total') / pl.col('prev_shares_total') - 1).abs())
            .otherwise(0.0)
            .alias('shares_change_ratio'),
        ])
        
        # 分类分红类型
        df = df.with_columns([
            pl.when(~pl.col('has_factor_change'))
            .then(pl.lit('none'))
            .when(pl.col('shares_change_ratio') < self.SHARES_CHANGE_THRESHOLD)
            .then(pl.lit('cash'))
            .otherwise(pl.lit('split'))
            .alias('dividend_type'),
        ])
        
        return df
    
    def _calculate_dividend_amounts(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        计算分红金额和送转股数
        """
        # 现金分红计算
        # 公式: 每股分红 = 昨日收盘价 * (1 - 昨日因子/今日因子)
        df = df.with_columns([
            pl.when(pl.col('dividend_type') == 'cash')
            .then(pl.col('prev_close') * (1 - pl.col('prev_factor') / pl.col('curr_factor')))
            .otherwise(0.0)
            .alias('dividend_per_share'),
        ])
        
        # 总分红金额
        df = df.with_columns([
            (pl.col('dividend_per_share') * pl.col('shares')).alias('total_dividend'),
        ])
        
        # 送转股计算
        # 公式: 新股数 = 原股数 * (今日因子 / 昨日因子)
        df = df.with_columns([
            pl.when(pl.col('dividend_type') == 'split')
            .then((pl.col('shares') * pl.col('curr_factor') / pl.col('prev_factor')).round().cast(pl.Int64))
            .otherwise(pl.col('shares'))
            .alias('new_shares'),
        ])
        
        return df
    
    def _to_dividend_events(
        self,
        df: pl.DataFrame,
        date_str: str
    ) -> List[DividendEvent]:
        """
        将 DataFrame 转换为 DividendEvent 列表
        """
        events = []
        
        # 只处理有分红的记录
        dividend_df = df.filter(pl.col('dividend_type').is_in(['cash', 'split']))
        
        for row in dividend_df.iter_rows(named=True):
            event = DividendEvent(
                stock_code=row['stock_code'],
                date=date_str,
                dividend_type=row['dividend_type'],
                dividend_per_share=row.get('dividend_per_share', 0.0),
                total_dividend=row.get('total_dividend', 0.0),
                old_shares=row['shares'],
                new_shares=row.get('new_shares', row['shares']),
                factor_change=row.get('factor_ratio', 1.0)
            )
            events.append(event)
        
        return events
    
    def apply_dividends(
        self,
        portfolio: Dict[str, int],
        events: List[DividendEvent]
    ) -> Tuple[Dict[str, int], float]:
        """
        应用分红事件到持仓
        
        Returns:
            (new_portfolio, cash_adjustment)
        """
        new_portfolio = portfolio.copy()
        cash_adjustment = 0.0
        
        for event in events:
            if event.dividend_type == 'cash':
                # 现金分红：增加现金
                cash_adjustment += event.total_dividend
                
            elif event.dividend_type == 'split':
                # 送转股：更新持仓数量
                if event.stock_code in new_portfolio:
                    new_portfolio[event.stock_code] = event.new_shares
        
        return new_portfolio, cash_adjustment
    
    def get_dividend_summary(
        self,
        events: List[DividendEvent]
    ) -> Dict[str, Any]:
        """
        获取分红汇总信息
        """
        cash_events = [e for e in events if e.dividend_type == 'cash']
        split_events = [e for e in events if e.dividend_type == 'split']
        
        total_cash = sum(e.total_dividend for e in cash_events)
        
        return {
            'total_events': len(events),
            'cash_dividends': len(cash_events),
            'split_events': len(split_events),
            'total_cash_dividend': total_cash,
            'affected_stocks': [e.stock_code for e in events],
        }
    
    def get_perf_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        calls = self._perf_stats['total_calls']
        return {
            'total_calls': calls,
            'total_duration': self._perf_stats['total_duration'],
            'avg_duration': self._perf_stats['total_duration'] / calls if calls > 0 else 0,
            'total_events': self._perf_stats['total_events'],
            'events_per_call': self._perf_stats['total_events'] / calls if calls > 0 else 0,
        }
    
    def print_perf_stats(self):
        """打印性能统计"""
        stats = self.get_perf_stats()
        print("=" * 60)
        print("向量化分红计算器性能统计")
        print("=" * 60)
        print(f"总调用次数: {stats['total_calls']}")
        print(f"总耗时: {stats['total_duration']:.3f} 秒")
        print(f"平均每次: {stats['avg_duration']*1000:.3f} ms")
        print(f"总事件数: {stats['total_events']}")
        print(f"每次平均: {stats['events_per_call']:.2f} 个")
        print("=" * 60)


# ==================== 便捷函数 ====================

def calculate_dividends_vectorized(
    portfolio: Dict[str, int],
    prev_day_data: pl.DataFrame,
    curr_day_data: pl.DataFrame,
    date_str: str
) -> Tuple[List[DividendEvent], float]:
    """
    便捷的向量化分红计算函数
    
    Returns:
        (dividend_events, cash_adjustment)
    """
    calculator = DividendCalculator()
    events = calculator.calculate_dividends(
        portfolio, prev_day_data, curr_day_data, date_str
    )
    
    _, cash_adjustment = calculator.apply_dividends(portfolio, events)
    
    return events, cash_adjustment


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("向量化分红结算模块测试")
    print("=" * 60)
    
    # 创建测试数据
    # 场景 1: 现金分红 (因子变化小)
    # 场景 2: 送转股 (因子变化大)
    # 场景 3: 无分红
    
    prev_day = pl.DataFrame({
        'stock_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
        'adj_factor': [1.0, 1.0, 1.0],
        'close': [10.0, 20.0, 30.0],
        'total_mv': [1e10, 2e10, 3e10],
    })
    
    # 000001: 现金分红 (因子从 1.0 变为 1.05，股本不变)
    # 000002: 送转股 (因子从 1.0 变为 1.5，股本增加 50%)
    # 000003: 无分红 (因子不变)
    curr_day = pl.DataFrame({
        'stock_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
        'adj_factor': [1.05, 1.5, 1.0],  # 因子变化
        'close': [9.52, 13.33, 30.0],    # 价格相应调整
        'total_mv': [1e10, 3e10, 3e10],  # 000002 股本增加 50%
    })
    
    # 持仓
    portfolio = {
        '000001.SZ': 1000,
        '000002.SZ': 2000,
        '000003.SZ': 3000,
    }
    
    # 创建计算器
    calculator = DividendCalculator()
    
    # 计算分红
    print("\n[测试] 计算分红事件...")
    events = calculator.calculate_dividends(
        portfolio=portfolio,
        prev_day_data=prev_day,
        curr_day_data=curr_day,
        date_str='2024-01-15'
    )
    
    print(f"  发现 {len(events)} 个分红事件:")
    for event in events:
        if event.dividend_type == 'cash':
            print(f"    {event.stock_code}: 现金分红 ¥{event.total_dividend:.2f} "
                  f"(每股 ¥{event.dividend_per_share:.4f})")
        elif event.dividend_type == 'split':
            print(f"    {event.stock_code}: 送转股 {event.old_shares} -> {event.new_shares} 股")
    
    # 应用分红
    print("\n[测试] 应用分红...")
    new_portfolio, cash_adj = calculator.apply_dividends(portfolio, events)
    
    print(f"  现金调整: +¥{cash_adj:.2f}")
    print(f"  持仓变化:")
    for code in portfolio:
        old = portfolio[code]
        new = new_portfolio.get(code, 0)
        if old != new:
            print(f"    {code}: {old} -> {new}")
        else:
            print(f"    {code}: {old} (无变化)")
    
    # 汇总信息
    print("\n[测试] 分红汇总...")
    summary = calculator.get_dividend_summary(events)
    print(f"  总事件数: {summary['total_events']}")
    print(f"  现金分红: {summary['cash_dividends']} 次")
    print(f"  送转股: {summary['split_events']} 次")
    print(f"  总现金分红: ¥{summary['total_cash_dividend']:.2f}")
    
    # 性能统计
    print("\n")
    calculator.print_perf_stats()
    
    print("\n测试完成!")
