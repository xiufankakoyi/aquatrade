import pandas as pd
from core.strategies.strategy_framework import StrategyBase
from core.backtest.flexible_backtest_engine import FlexibleBacktestEngine
from data_svc.database.optimized_data_query import OptimizedStockDataQuery
import tqdm

class PurePandasStrategy(StrategyBase):
    """
    一个典型的旧式策略，完全依赖 Pandas 语法，且不包含 prefer_polars = True
    """
    def __init__(self):
        super().__init__()
        self.name = "PurePandasStrategy"

    def generate_signals(self, current_date, stock_pool_today, data_query):
        # 如果 stock_pool_today 是 Polars，这里会崩溃
        # 我们使用 ILOC 这一典型的 Pandas 语法来测试
        if stock_pool_today is not None and len(stock_pool_today) > 0:
            # 故意使用 .iloc 和 Pandas 布尔过滤
            sample = stock_pool_today.iloc[0] 
            code = sample['stock_code']
            return {code: {'action': 'buy'}}
        return {}

def test_compatibility():
    print("=" * 80)
    print("Legacy Pandas Strategy 兼容性测试")
    print("=" * 80)
    
    query = OptimizedStockDataQuery()
    engine = FlexibleBacktestEngine(data_query=query, initial_capital=100000)
    strategy = PurePandasStrategy()
    
    # 运行简短回测
    start_date = "2024-01-01"
    end_date = "2024-01-05"
    
    print(f"开始回测: {start_date} 到 {end_date}...")
    try:
        # 正确参数顺序: start_date, end_date, strategy
        results = list(engine.run_backtest_streaming(
            start_date,
            end_date,
            strategy
        ))
        print("✅ 回测完成，未发生崩溃。兼容性逻辑生效。")
    except Exception as e:
        print(f"❌ 回测崩溃: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_compatibility()
