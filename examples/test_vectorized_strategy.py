# examples/test_vectorized_strategy.py
"""
向量化策略测试示例

演示如何使用新的向量化架构
"""

import pandas as pd
import numpy as np
from strategies.vectorized_strategy_base import VectorizedStrategyBase
from utils.indicator_calculator import IndicatorCalculator


class SimpleMAStrategy(VectorizedStrategyBase):
    """
    简单的MA策略示例
    
    策略逻辑：
    - 收盘价 > MA20：买入
    - 收盘价 < MA5：卖出
    """
    
    strategy_name = "简单MA策略"
    
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self.indicator_calculator = IndicatorCalculator()
    
    def generate_signals_vectorized(
        self,
        market_matrix: pd.DataFrame,
        current_date: str
    ) -> pd.Series:
        """向量化生成信号"""
        if market_matrix.empty:
            return pd.Series(dtype=str)
        
        # 获取最新日期
        latest_date = market_matrix.index.get_level_values(1).max()
        
        # 方法1：使用指标计算器（推荐）
        indicators_df = self.indicator_calculator.calculate_batch(
            market_matrix.reset_index(),
            [
                {'type': 'ma', 'column': 'close', 'window': 5, 'name': 'ma5'},
                {'type': 'ma', 'column': 'close', 'window': 20, 'name': 'ma20'},
            ],
            group_by='stock_code'
        )
        
        # 获取最新日期的指标值
        latest_indicators = indicators_df[
            indicators_df['trade_date'] == latest_date
        ].set_index('stock_code')
        
        snapshot = market_matrix.xs(latest_date, level=1)
        
        # 初始化信号
        signals = pd.Series('hold', index=snapshot.index)
        
        # 向量化条件判断
        close = snapshot['close']
        ma5 = latest_indicators['ma5']
        ma20 = latest_indicators['ma20']
        
        # 买入：收盘价 > MA20
        buy_mask = close > ma20
        signals[buy_mask] = 'buy'
        
        # 卖出：收盘价 < MA5
        sell_mask = close < ma5
        signals[sell_mask] = 'sell'
        
        return signals


def create_sample_market_matrix():
    """
    创建示例市场矩阵数据（用于测试）
    
    返回：
        pd.DataFrame with MultiIndex (stock_code, trade_date)
    """
    # 生成示例数据
    dates = pd.date_range('2023-01-01', '2023-01-10', freq='D')
    codes = ['000001', '000002', '600000']
    
    data = []
    for code in codes:
        for date in dates:
            # 生成随机价格数据
            base_price = 10.0 + np.random.randn() * 2
            data.append({
                'stock_code': code,
                'trade_date': date,
                'open': base_price + np.random.randn() * 0.5,
                'high': base_price + abs(np.random.randn() * 0.5),
                'low': base_price - abs(np.random.randn() * 0.5),
                'close': base_price + np.random.randn() * 0.3,
                'volume': 1000000 + np.random.randint(-100000, 100000),
            })
    
    df = pd.DataFrame(data)
    df = df.set_index(['stock_code', 'trade_date'])
    df = df.sort_index()
    
    return df


if __name__ == '__main__':
    # 创建示例数据
    market_matrix = create_sample_market_matrix()
    print("市场矩阵形状:", market_matrix.shape)
    print("\n市场矩阵预览:")
    print(market_matrix.head(10))
    
    # 创建策略
    strategy = SimpleMAStrategy()
    
    # 生成信号
    signals = strategy.generate_signals_vectorized(
        market_matrix,
        current_date='2023-01-10'
    )
    
    print("\n生成的信号:")
    print(signals)
    print(f"\n买入信号数量: {(signals == 'buy').sum()}")
    print(f"卖出信号数量: {(signals == 'sell').sum()}")
    print(f"持有信号数量: {(signals == 'hold').sum()}")


