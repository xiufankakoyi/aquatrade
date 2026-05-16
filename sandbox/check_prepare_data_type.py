"""
检查 prepare_data 返回的数据类型
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategies.vectorized_base import VectorizedStrategyBase
from data_svc.database.optimized_data_query import OptimizedStockDataQuery


class TestStrategy(VectorizedStrategyBase):
    strategy_id = "test"
    strategy_name = "测试策略"
    
    def generate_signals_vectorized(self, price_matrix, trading_dates, stock_codes, data_query, preloaded_data=None):
        self.prepare_data(preloaded_data, trading_dates, stock_codes, price_matrix)
        
        print(f"\n数据类型检查:")
        print(f"  close type: {type(self.close)}")
        print(f"  close dtype: {self.close.dtype if hasattr(self.close, 'dtype') else 'N/A'}")
        print(f"  ma5 type: {type(self.ma5)}")
        print(f"  ma5 dtype: {self.ma5.dtype if hasattr(self.ma5, 'dtype') else 'N/A'}")
        
        if isinstance(self.ma5, np.ndarray):
            print(f"  ma5 shape: {self.ma5.shape}")
            print(f"  ma5 nan count: {np.sum(np.isnan(self.ma5))}")
            print(f"  ma5 valid count: {np.sum(~np.isnan(self.ma5))}")
        
        return np.zeros((len(trading_dates), len(stock_codes)), dtype=np.int8)


def main():
    print("=" * 80)
    print("检查 prepare_data 返回类型")
    print("=" * 80)
    
    data_query = OptimizedStockDataQuery()
    
    start_date = "2024-01-01"
    end_date = "2024-01-10"
    
    data_query.preload_backtest_data(start_date, end_date)
    preloaded = getattr(data_query, '_preloaded_data', None)
    
    if preloaded is None:
        print("预加载数据为空")
        return
    
    trading_dates = sorted(preloaded.keys())
    stock_codes = sorted(list(set(
        code for df in preloaded.values() 
        for code in df['stock_code'].unique()
    )))
    
    T = len(trading_dates)
    N = len(stock_codes)
    price_matrix = np.zeros((T, N, 4), dtype=np.float32)
    
    strategy = TestStrategy()
    strategy.generate_signals_vectorized(price_matrix, trading_dates, stock_codes, data_query, preloaded)


if __name__ == "__main__":
    main()
